const app = getApp();

function decodeQueryValue(value, fallback = '') {
  if (!value) return fallback;
  try {
    return decodeURIComponent(value);
  } catch (e) {
    console.warn('分享参数解码失败:', e);
    return fallback;
  }
}

function isValidTaskId(value) {
  return /^[0-9a-f]{32}$/.test(value || '');
}

Page({
  data: {
    quota: 10,
    isVip: false,
    templates: [],
    selectedTemplate: 'kiss',
    selectedTemplateTitle: '飞吻',
    selectedTemplateDesc: '发送爱心，萌力爆表',
    showTemplateDrawer: false,
    mode: 'upload', // 'upload' | 'sketch'
    refImagePath: '',
    characterDesc: '',
    caption: '么么哒',
    customActionText: '',
    isGenerating: false,
    progress: 0,
    stageText: '',
    gifResultUrl: '',
    gifLoaded: false,
    gifWarning: '',
    taskId: '',
    showFullScreenSketch: false,
    fsColor: '#1e293b',
    fsLineWidth: 6,
    sketchTempPath: '',
    showFavoriteTip: true,
    showCollectionModal: false,
    userCollections: [],
    selectedColId: '',
    newColTitle: '',
    showAdvDesc: false,

    // 动态生成规格控制
    currentFrameCount: 16,
    currentResolution: '240x240',
    showSpecsSheet: false,

    // 动态拟合耗时进度条
    elapsedSeconds: 0,
    estimatedSeconds: 32,

    // 好友分享成品直出
    sharedFromFriend: false,
    sharedGifTitle: ''
  },

  onLoad(options) {
    if (options && options.inviter) {
      app.globalData.inviterCode = options.inviter;
    }
    // 微信好友点击分享链接：优先直出动图成品，彻底杜绝跳过成品直接载入模板的体验 Bug
    if (options && isValidTaskId(options.share_task)) {
      const sharedTitle = decodeQueryValue(options.share_title, '专属动图');
      this.setData({
        taskId: options.share_task,
        gifResultUrl: app.toAbsoluteUrl(`/outputs/${options.share_task}/meme_result.gif`),
        caption: sharedTitle,
        sharedFromFriend: true,
        sharedGifTitle: sharedTitle
      });
      if (options.ref_tpl) {
        wx.setStorageSync('preselect_tpl', { id: decodeQueryValue(options.ref_tpl) });
      }
    } else if (options && options.share_gif) {
      const sharedUrl = decodeQueryValue(options.share_gif);
      const sharedTitle = decodeQueryValue(options.share_title, '专属动图');
      this.setData({
        gifResultUrl: sharedUrl,
        caption: sharedTitle,
        sharedFromFriend: true,
        sharedGifTitle: sharedTitle
      });
      if (options.ref_tpl) {
        wx.setStorageSync('preselect_tpl', { id: options.ref_tpl });
      }
    } else if (options && options.ref_tpl) {
      wx.setStorageSync('preselect_tpl', { id: options.ref_tpl });
    }
    const dismissed = wx.getStorageSync('dismiss_fav_tip');
    if (dismissed) {
      this.setData({ showFavoriteTip: false });
    }
    this.fetchTemplates();
    this.updateQuotaInfo();
    this.initSketchCanvas();
    this.checkResumeActiveTask();
  },

  onShow() {
    this.updateQuotaInfo();
    this.checkResumeActiveTask();
    const cfg = app.getGifConfig();
    this.setData({
      currentFrameCount: cfg.frameCount || 16,
      currentResolution: cfg.resolution || '240x240'
    });
    if (app.globalData.tempEditedImage) {
      this.setData({
        refImagePath: app.globalData.tempEditedImage
      });
      app.globalData.tempEditedImage = null;
    }

    const preselect = wx.getStorageSync('preselect_tpl');
    if (preselect && preselect.id) {
      wx.removeStorageSync('preselect_tpl');
      const found = (this.data.templates || []).find(t => t.id === preselect.id);
      if (found) {
        this.setData({
          selectedTemplate: found.id,
          selectedTemplateTitle: found.title,
          selectedTemplateDesc: found.action,
          caption: preselect.caption || found.default_caption || this.data.caption
        });
      } else {
        this.setData({
          selectedTemplate: preselect.id,
          caption: preselect.caption || this.data.caption
        });
      }
      wx.showToast({ title: '已载入同款模板', icon: 'success' });
    }
  },

  checkResumeActiveTask() {
    const activeTask = wx.getStorageSync('active_meme_task');
    if (!activeTask || !activeTask.taskId) return;
    
    // 如果任务超过 5 分钟，视为已过期或结束
    const now = Date.now();
    if (now - (activeTask.timestamp || 0) > 5 * 60 * 1000) {
      wx.removeStorageSync('active_meme_task');
      return;
    }

    if (!this.data.isGenerating && !this.data.gifResultUrl) {
      this.setData({
        isGenerating: true,
        taskId: activeTask.taskId,
        progress: 30,
        stageText: '正在恢复后台任务进度...'
      });
      this.pollTaskStatus(activeTask.taskId);
    }
  },

  onPullDownRefresh() {
    this.updateQuotaInfo(() => {
      wx.stopPullDownRefresh();
    });
  },

  updateQuotaInfo(cb) {
    app.fetchUserProfile(null, (user) => {
      this.setData({
        quota: user.total_quota || 0,
        isVip: user.is_vip === 1
      });
      if (cb) cb();
    });
  },

  fetchTemplates() {
    app.request({
      url: `${app.globalData.baseURL}/api/templates`,
      method: 'GET',
      success: (res) => {
        if (res.data && res.data.data) {
          const list = res.data.data;
          const current = list.find(t => t.id === this.data.selectedTemplate) || list[0] || {};
          this.setData({
            templates: list,
            selectedTemplate: current.id || this.data.selectedTemplate,
            selectedTemplateTitle: current.title || '飞吻',
            selectedTemplateDesc: current.action || '发送爱心，萌力爆表'
          });
        }
      }
    });
  },

  openTemplateDrawer() {
    this.setData({ showTemplateDrawer: true });
  },

  closeTemplateDrawer() {
    this.setData({ showTemplateDrawer: false });
  },

  selectTemplate(e) {
    const { id, title, desc, caption } = e.currentTarget.dataset;
    this.setData({
      selectedTemplate: id,
      selectedTemplateTitle: title || id,
      selectedTemplateDesc: desc || this.data.selectedTemplateDesc,
      caption: caption || this.data.caption
    });
  },

  selectTemplateFromDrawer(e) {
    this.selectTemplate(e);
    this.closeTemplateDrawer();
  },

  onInputCustomAction(e) {
    this.setData({ customActionText: e.detail.value });
  },

  pickCustomActionIdea() {
    const ideas = [
      '双手叉腰仰天长笑，眼角笑出泪花',
      '委屈巴巴揉眼睛抹眼泪，嘴巴扁扁抽泣',
      '双手竖起大拇指疯狂点赞，伴随节奏摇摆',
      '双手捧咖啡慢慢吹气轻啜，满脸惬意享受',
      '震惊地张大嘴巴双手抱头，双眼瞪圆如铜铃',
      '双手作揖连连拜谢，身体不断前倾作揖',
      '拿着放大镜探头探脑，好奇地左顾右盼暗中观察'
    ];
    wx.showActionSheet({
      itemList: ideas,
      success: (res) => {
        this.setData({ customActionText: ideas[res.tapIndex] });
      }
    });
  },

  switchMode(e) {
    const mode = e.currentTarget.dataset.mode;
    this.setData({ mode });
    if (mode === 'sketch') {
      setTimeout(() => this.initSketchCanvas(), 200);
    }
  },

  // --- 图片上传与裁剪 ---
  chooseImage() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      success: (res) => {
        if (res.tempFiles && res.tempFiles.length > 0) {
          this.setData({
            refImagePath: res.tempFiles[0].tempFilePath
          });
        }
      }
    });
  },

  cropCurrentImage() {
    if (!this.data.refImagePath) return;
    this.openImageEditor(true);
  },

  openImageEditor(isCropMode = false) {
    const src = this.data.refImagePath ? encodeURIComponent(this.data.refImagePath) : '';
    const modeParam = (isCropMode === true || (isCropMode && isCropMode.type === undefined && isCropMode)) ? '&mode=crop' : '';
    wx.navigateTo({
      url: `/pages/editor/editor?src=${src}${modeParam}`
    });
  },

  openSpecsSheet() {
    this.setData({ showSpecsSheet: true });
  },

  closeSpecsSheet() {
    this.setData({ showSpecsSheet: false });
  },

  selectFrameCount(e) {
    const count = Number(e.currentTarget.dataset.count);
    app.setGifConfig({ frameCount: count });
    this.setData({ currentFrameCount: count });
    wx.showToast({ title: `已设为 ${count} 帧`, icon: 'success' });
  },

  selectResolution(e) {
    const res = e.currentTarget.dataset.res;
    app.setGifConfig({ resolution: res });
    this.setData({ currentResolution: res });
    wx.showToast({ title: `已设为 ${res}`, icon: 'success' });
  },

  dismissSharedBanner() {
    this.setData({ sharedFromFriend: false });
  },

  removeImage() {
    this.setData({ refImagePath: '' });
  },

  onInputDesc(e) {
    this.setData({ characterDesc: e.detail.value });
  },

  onInputCaption(e) {
    this.setData({ caption: e.detail.value });
  },

  quickPickCaption(e) {
    const text = e.currentTarget.dataset.text;
    if (text) {
      this.setData({ caption: text });
      wx.showToast({ title: '已填入台词', icon: 'none', duration: 1000 });
    }
  },

  toggleShowAdvDesc() {
    this.setData({ showAdvDesc: !this.data.showAdvDesc });
  },

  getCaptionSuggestions() {
    wx.showLoading({ title: '正在提取灵感...' });
    app.request({
      url: `${app.globalData.baseURL}/api/convert/caption-suggest`,
      method: 'POST',
      header: { 'content-type': 'application/x-www-form-urlencoded' },
      data: { keyword: this.data.characterDesc || '摸鱼' },
      success: (res) => {
        wx.hideLoading();
        if (res.data && res.data.suggestions && res.data.suggestions.length > 0) {
          const suggestions = res.data.suggestions;
          // 微信 showActionSheet 限制每项文案长度，超长做截断显示，但点击时存入完整原文
          const items = suggestions.map(s => {
            const label = `[${s.style}] ${s.text}`;
            return label.length > 18 ? label.slice(0, 17) + '…' : label;
          });
          wx.showActionSheet({
            itemList: items,
            success: (aRes) => {
              const picked = suggestions[aRes.tapIndex].text;
              this.setData({ caption: picked });
              wx.showToast({ title: '已套用灵感台词', icon: 'success' });
            }
          });
        } else {
          wx.showToast({ title: '暂无更多灵感', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '提取灵感失败', icon: 'none' });
      }
    });
  },

  // --- 草图画板实现 (黑笔白底) ---
  initSketchCanvas() {
    const query = wx.createSelectorQuery();
    query.select('#sketchCanvas')
      .fields({ node: true, size: true })
      .exec((res) => {
        if (!res[0] || !res[0].node) return;
        const canvas = res[0].node;
        const ctx = canvas.getContext('2d');
        const windowInfo = (wx.getWindowInfo && wx.getWindowInfo()) || (wx.getSystemInfoSync ? wx.getSystemInfoSync() : {});
        const dpr = windowInfo.pixelRatio || 2;
        canvas.width = res[0].width * dpr;
        canvas.height = res[0].height * dpr;
        ctx.scale(dpr, dpr);
        ctx.strokeStyle = '#1e293b';
        ctx.lineWidth = 4;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        this.sketchCanvas = canvas;
        this.sketchCtx = ctx;
        this.sketchStrokes = [];
        this.sketchRedoStack = [];
      });
  },

  onSketchStart(e) {
    if (!this.sketchCtx) return;
    const touch = e.touches[0];
    this.currentSketchStroke = {
      color: '#1e293b',
      width: 4,
      points: [{ x: touch.x, y: touch.y }]
    };
    this.sketchCtx.beginPath();
    this.sketchCtx.strokeStyle = '#1e293b';
    this.sketchCtx.lineWidth = 4;
    this.sketchCtx.lineCap = 'round';
    this.sketchCtx.lineJoin = 'round';
    this.sketchCtx.moveTo(touch.x, touch.y);
  },

  onSketchMove(e) {
    if (!this.sketchCtx || !this.currentSketchStroke) return;
    const touch = e.touches[0];
    this.currentSketchStroke.points.push({ x: touch.x, y: touch.y });
    this.sketchCtx.lineTo(touch.x, touch.y);
    this.sketchCtx.stroke();
  },

  onSketchEnd() {
    if (!this.sketchCtx || !this.currentSketchStroke) return;
    this.sketchCtx.closePath();
    if (!this.sketchStrokes) this.sketchStrokes = [];
    if (this.currentSketchStroke.points.length > 0) {
      this.sketchStrokes.push(this.currentSketchStroke);
      this.sketchRedoStack = [];
    }
    this.currentSketchStroke = null;
  },

  redrawSketch() {
    if (!this.sketchCanvas || !this.sketchCtx) return;
    const windowInfo = (wx.getWindowInfo && wx.getWindowInfo()) || (wx.getSystemInfoSync ? wx.getSystemInfoSync() : {});
    const dpr = windowInfo.pixelRatio || 2;
    this.sketchCtx.clearRect(0, 0, this.sketchCanvas.width / dpr, this.sketchCanvas.height / dpr);

    if (!this.sketchStrokes || this.sketchStrokes.length === 0) return;
    for (const stroke of this.sketchStrokes) {
      if (!stroke.points || stroke.points.length === 0) continue;
      this.sketchCtx.save();
      this.sketchCtx.strokeStyle = stroke.color || '#1e293b';
      this.sketchCtx.lineWidth = stroke.width || 4;
      this.sketchCtx.lineCap = 'round';
      this.sketchCtx.lineJoin = 'round';
      this.sketchCtx.beginPath();
      this.sketchCtx.moveTo(stroke.points[0].x, stroke.points[0].y);
      for (let i = 1; i < stroke.points.length; i++) {
        this.sketchCtx.lineTo(stroke.points[i].x, stroke.points[i].y);
      }
      this.sketchCtx.stroke();
      this.sketchCtx.restore();
    }
  },

  undoSketch() {
    if (!this.sketchStrokes || this.sketchStrokes.length === 0) {
      wx.showToast({ title: '无可撤销笔画', icon: 'none' });
      return;
    }
    if (!this.sketchRedoStack) this.sketchRedoStack = [];
    const stroke = this.sketchStrokes.pop();
    this.sketchRedoStack.push(stroke);
    this.redrawSketch();
    wx.showToast({ title: '已撤销', icon: 'none', duration: 600 });
  },

  redoSketch() {
    if (!this.sketchRedoStack || this.sketchRedoStack.length === 0) {
      wx.showToast({ title: '无可前进笔画', icon: 'none' });
      return;
    }
    if (!this.sketchStrokes) this.sketchStrokes = [];
    const stroke = this.sketchRedoStack.pop();
    this.sketchStrokes.push(stroke);
    this.redrawSketch();
    wx.showToast({ title: '已恢复', icon: 'none', duration: 600 });
  },

  clearSketch() {
    if (!this.sketchCanvas || !this.sketchCtx) return;
    this.sketchStrokes = [];
    this.sketchRedoStack = [];
    const windowInfo = (wx.getWindowInfo && wx.getWindowInfo()) || (wx.getSystemInfoSync ? wx.getSystemInfoSync() : {});
    const dpr = windowInfo.pixelRatio || 2;
    this.sketchCtx.clearRect(0, 0, this.sketchCanvas.width / dpr, this.sketchCanvas.height / dpr);
    this.setData({ sketchTempPath: '' });
    wx.showToast({ title: '画板已清空', icon: 'none' });
  },

  // --- 全屏涂鸦画板 ---
  openFullScreenSketch() {
    try {
      wx.hideTabBar({ animation: true });
    } catch (e) {}
    this.setData({ showFullScreenSketch: true });
    setTimeout(() => {
      this.initFullScreenCanvas();
    }, 200);
  },

  closeFullScreenSketch() {
    try {
      wx.showTabBar({ animation: true });
    } catch (e) {}
    this.setData({ showFullScreenSketch: false });
  },

  initFullScreenCanvas() {
    this.fsStrokes = [];
    this.fsRedoStack = [];
    const query = wx.createSelectorQuery();
    query.select('#fullScreenCanvas')
      .fields({ node: true, size: true })
      .exec((res) => {
        if (!res[0] || !res[0].node) return;
        const canvas = res[0].node;
        const ctx = canvas.getContext('2d');
        const windowInfo = (wx.getWindowInfo && wx.getWindowInfo()) || (wx.getSystemInfoSync ? wx.getSystemInfoSync() : {});
        const dpr = windowInfo.pixelRatio || 2;
        canvas.width = res[0].width * dpr;
        canvas.height = res[0].height * dpr;
        ctx.scale(dpr, dpr);
        ctx.strokeStyle = this.data.fsColor || '#1e293b';
        ctx.lineWidth = this.data.fsLineWidth || 6;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        this.fsCanvas = canvas;
        this.fsCtx = ctx;

        // 若之前有临时画作，加载并绘制到底布
        if (this.data.sketchTempPath) {
          const img = canvas.createImage();
          img.onload = () => {
            this.fsBaseImageObj = img;
            ctx.drawImage(img, 0, 0, res[0].width, res[0].height);
          };
          img.src = this.data.sketchTempPath;
        } else {
          this.fsBaseImageObj = null;
        }
      });
  },

  onFSSketchStart(e) {
    if (!this.fsCtx) return;
    const touch = e.touches[0];
    this.currentFSStroke = {
      color: this.data.fsColor || '#1e293b',
      width: this.data.fsLineWidth || 6,
      points: [{ x: touch.x, y: touch.y }]
    };
    this.fsCtx.beginPath();
    this.fsCtx.strokeStyle = this.data.fsColor || '#1e293b';
    this.fsCtx.lineWidth = this.data.fsLineWidth || 6;
    this.fsCtx.lineCap = 'round';
    this.fsCtx.lineJoin = 'round';
    this.fsCtx.moveTo(touch.x, touch.y);
  },

  onFSSketchMove(e) {
    if (!this.fsCtx || !this.currentFSStroke) return;
    const touch = e.touches[0];
    this.currentFSStroke.points.push({ x: touch.x, y: touch.y });
    this.fsCtx.lineTo(touch.x, touch.y);
    this.fsCtx.stroke();
  },

  onFSSketchEnd() {
    if (!this.fsCtx || !this.currentFSStroke) return;
    this.fsCtx.closePath();
    if (!this.fsStrokes) this.fsStrokes = [];
    if (this.currentFSStroke.points.length > 0) {
      this.fsStrokes.push(this.currentFSStroke);
      this.fsRedoStack = [];
    }
    this.currentFSStroke = null;
  },

  redrawFSSketch() {
    if (!this.fsCanvas || !this.fsCtx) return;
    const windowInfo = (wx.getWindowInfo && wx.getWindowInfo()) || (wx.getSystemInfoSync ? wx.getSystemInfoSync() : {});
    const dpr = windowInfo.pixelRatio || 2;
    this.fsCtx.clearRect(0, 0, this.fsCanvas.width / dpr, this.fsCanvas.height / dpr);

    if (this.fsBaseImageObj) {
      this.fsCtx.drawImage(this.fsBaseImageObj, 0, 0, this.fsCanvas.width / dpr, this.fsCanvas.height / dpr);
    }

    if (!this.fsStrokes || this.fsStrokes.length === 0) return;
    for (const stroke of this.fsStrokes) {
      if (!stroke.points || stroke.points.length === 0) continue;
      this.fsCtx.save();
      this.fsCtx.strokeStyle = stroke.color;
      this.fsCtx.lineWidth = stroke.width;
      this.fsCtx.lineCap = 'round';
      this.fsCtx.lineJoin = 'round';
      this.fsCtx.beginPath();
      this.fsCtx.moveTo(stroke.points[0].x, stroke.points[0].y);
      for (let i = 1; i < stroke.points.length; i++) {
        this.fsCtx.lineTo(stroke.points[i].x, stroke.points[i].y);
      }
      this.fsCtx.stroke();
      this.fsCtx.restore();
    }
  },

  undoFSSketch() {
    if (!this.fsStrokes || this.fsStrokes.length === 0) {
      wx.showToast({ title: '无可撤销笔画', icon: 'none' });
      return;
    }
    if (!this.fsRedoStack) this.fsRedoStack = [];
    const stroke = this.fsStrokes.pop();
    this.fsRedoStack.push(stroke);
    this.redrawFSSketch();
    wx.showToast({ title: '已撤销', icon: 'none', duration: 600 });
  },

  redoFSSketch() {
    if (!this.fsRedoStack || this.fsRedoStack.length === 0) {
      wx.showToast({ title: '无可前进笔画', icon: 'none' });
      return;
    }
    if (!this.fsStrokes) this.fsStrokes = [];
    const stroke = this.fsRedoStack.pop();
    this.fsStrokes.push(stroke);
    this.redrawFSSketch();
    wx.showToast({ title: '已恢复', icon: 'none', duration: 600 });
  },

  setFSColor(e) {
    const color = e.currentTarget.dataset.color;
    this.setData({ fsColor: color });
    if (this.fsCtx) this.fsCtx.strokeStyle = color;
  },

  setFSLineWidth(e) {
    const w = Number(e.currentTarget.dataset.w);
    this.setData({ fsLineWidth: w });
    if (this.fsCtx) this.fsCtx.lineWidth = w;
  },

  clearFullScreenSketch() {
    if (!this.fsCanvas || !this.fsCtx) return;
    this.fsStrokes = [];
    this.fsRedoStack = [];
    this.fsBaseImageObj = null;
    const windowInfo = (wx.getWindowInfo && wx.getWindowInfo()) || (wx.getSystemInfoSync ? wx.getSystemInfoSync() : {});
    const dpr = windowInfo.pixelRatio || 2;
    this.fsCtx.clearRect(0, 0, this.fsCanvas.width / dpr, this.fsCanvas.height / dpr);
    this.setData({ sketchTempPath: '' });
    wx.showToast({ title: '画板已清空', icon: 'none' });
  },

  saveAndSyncFullScreenSketch() {
    try {
      wx.showTabBar({ animation: true });
    } catch (e) {}
    if (!this.fsCanvas) {
      this.closeFullScreenSketch();
      return;
    }
    wx.canvasToTempFilePath({
      canvas: this.fsCanvas,
      success: (res) => {
        this.setData({
          sketchTempPath: res.tempFilePath,
          showFullScreenSketch: false
        });
        if (this.sketchCanvas && this.sketchCtx) {
          const img = this.sketchCanvas.createImage();
          img.onload = () => {
            this.sketchCtx.clearRect(0, 0, this.sketchCanvas.width, this.sketchCanvas.height);
            this.sketchCtx.drawImage(img, 0, 0, 320, 220);
          };
          img.src = res.tempFilePath;
        }
        wx.showToast({ title: '全屏手绘已保存', icon: 'success' });
      },
      fail: () => {
        this.closeFullScreenSketch();
      }
    });
  },

  // --- 提交生成 ---
  startGenerate() {
    if (this.data.isGenerating) return;

    if (this.data.selectedTemplate === 'custom' && !this.data.customActionText.trim()) {
      wx.showToast({ title: '请填写自定义动作描述', icon: 'none' });
      return;
    }

    if (this.data.quota <= 0 && !this.data.isVip) {
      wx.showModal({
        title: '制作额度不足',
        content: '免费体验额度已用完，仅需 1.00 元即可开通 20 次超值尝鲜包，是否立即开通？',
        confirmText: '1元开通',
        cancelText: '每日签到',
        success: (mRes) => {
          if (mRes.confirm) {
            this.goToRecharge();
          } else {
            this.handleCheckin();
          }
        }
      });
      return;
    }

    // 微信订阅消息：如果已在后台配置模板ID，在点击时发起订阅
    const tmplId = app.globalData.subscribeTemplateId;
    if (tmplId && wx.requestSubscribeMessage) {
      wx.requestSubscribeMessage({
        tmplIds: [tmplId],
        complete: () => {
          this.executeGeneratePipeline();
        }
      });
    } else {
      this.executeGeneratePipeline();
    }
  },

  startSmoothProgressBar(estDuration) {
    if (this.smoothTimer) {
      clearInterval(this.smoothTimer);
      this.smoothTimer = null;
    }
    const targetSeconds = Math.max(15, estDuration || 32);
    const startTime = Date.now();
    this.setData({
      elapsedSeconds: 0,
      estimatedSeconds: targetSeconds,
      progress: 6,
      stageText: 'AI 极速渲染引擎启动中...'
    });

    this.smoothTimer = setInterval(() => {
      if (!this.data.isGenerating) {
        clearInterval(this.smoothTimer);
        this.smoothTimer = null;
        return;
      }
      const elapsed = Math.floor((Date.now() - startTime) / 1000);
      let p = 6;
      if (elapsed < targetSeconds) {
        p = Math.min(88, Math.round(6 + (elapsed / targetSeconds) * 80));
      } else {
        const extra = elapsed - targetSeconds;
        p = Math.min(95, Math.round(88 + (extra / 30) * 7));
      }

      let stage = this.data.stageText;
      if (p < 25) {
        stage = '正在解析形象并构建动态分镜...';
      } else if (p < 55) {
        stage = `正在逐帧生成 ${this.data.currentFrameCount} 帧动作序列...`;
      } else if (p < 85) {
        stage = '正在进行色彩量化与 GIF 编码封装...';
      } else {
        stage = '动图渲染即将就绪，正在呈现...';
      }

      this.setData({
        elapsedSeconds: elapsed,
        progress: Math.max(this.data.progress, p),
        stageText: stage
      });
    }, 500);
  },

  executeGeneratePipeline() {
    this.setData({
      isGenerating: true,
      progress: 5,
      stageText: '正在启动极速渲染引擎...',
      gifResultUrl: '',
      gifLoaded: false,
      gifWarning: '',
      elapsedSeconds: 0
    });

    const gifConfig = app.getGifConfig();
    const frameCount = gifConfig.frameCount || this.data.currentFrameCount || 16;
    const resolution = gifConfig.resolution || this.data.currentResolution || '240x240';

    const formData = {
      action_type: this.data.selectedTemplate,
      character_desc: this.data.characterDesc,
      custom_caption: this.data.caption,
      custom_action: this.data.customActionText ? this.data.customActionText.trim() : '',
      fps: gifConfig.fps || 8,
      resolution: resolution,
      frame_count: frameCount,
      fast_mode: gifConfig.fastMode ? '1' : '0',
      loop_count: gifConfig.loopCount || 0,
      openid: app.globalData.openid || '',
      is_sketch: this.data.mode === 'sketch' ? '1' : '0'
    };

    const uploadUrl = `${app.globalData.baseURL}/api/generate-async`;

    if (this.data.mode === 'upload' && this.data.refImagePath) {
      app.uploadFile({
        url: uploadUrl,
        filePath: this.data.refImagePath,
        name: 'ref_image',
        formData: formData,
        success: (res) => {
          this.handleTaskResponse(res.data);
        },
        fail: (err) => {
          this.handleGenerateError("网络传输超时，请重试");
        }
      });
    } else if (this.data.mode === 'sketch') {
      const sketchFile = this.data.sketchTempPath;
      if (sketchFile) {
        app.uploadFile({
          url: uploadUrl,
          filePath: sketchFile,
          name: 'ref_image',
          formData: formData,
          success: (res) => {
            this.handleTaskResponse(res.data);
          },
          fail: () => {
            this.handleGenerateError("草图传输超时");
          }
        });
      } else if (this.sketchCanvas) {
        wx.canvasToTempFilePath({
          canvas: this.sketchCanvas,
          success: (cRes) => {
            app.uploadFile({
              url: uploadUrl,
              filePath: cRes.tempFilePath,
              name: 'ref_image',
              formData: formData,
              success: (res) => {
                this.handleTaskResponse(res.data);
              },
              fail: () => {
                this.handleGenerateError("草图传输超时");
              }
            });
          },
          fail: () => {
            this.postFormGenerate(uploadUrl, formData);
          }
        });
      } else {
        this.postFormGenerate(uploadUrl, formData);
      }
    } else {
      this.postFormGenerate(uploadUrl, formData);
    }
  },

  postFormGenerate(url, formData) {
    app.request({
      url: url,
      method: 'POST',
      header: { 'content-type': 'application/x-www-form-urlencoded' },
      data: formData,
      success: (res) => {
        this.handleTaskResponse(res.data);
      },
      fail: () => {
        this.handleGenerateError("网络连接失败");
      }
    });
  },

  handleTaskResponse(raw) {
    let data = raw;
    if (typeof raw === 'string') {
      try { data = JSON.parse(raw); } catch(e) {}
    }

    if (data && data.data && data.data.task_id) {
      const taskId = data.data.task_id;
      const est = (data.data && data.data.estimated_duration) ? Math.round(data.data.estimated_duration) : 32;
      this.setData({ 
        taskId,
        estimatedSeconds: est,
        elapsedSeconds: 0
      });
      wx.setStorageSync('active_meme_task', {
        taskId: taskId,
        timestamp: Date.now()
      });
      this.startSmoothProgressBar(est);
      this.pollTaskStatus(taskId);
      this.updateQuotaInfo();
    } else {
      this.handleGenerateError((data && data.detail) || "启动任务失败");
    }
  },

  pollTaskStatus(taskId) {
    if (!taskId) return;

    // 清理可能已有的轮询器，避免并发定时器与网络请求排队
    if (this.pollTimeout) {
      clearTimeout(this.pollTimeout);
      this.pollTimeout = null;
    }
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }

    this._pollingTaskId = taskId;
    this._isTaskFinalized = false;
    this._isRequestingStatus = false;

    const pollStep = () => {
      // 若任务已锁定终结、任务ID变更或非生成状态，则彻底退出轮询
      if (this._isTaskFinalized || this._pollingTaskId !== taskId || !this.data.isGenerating) {
        return;
      }

      // 若上一次网络请求尚未返回，跳过当前时钟周期，杜绝请求并发堆叠
      if (this._isRequestingStatus) {
        this.pollTimeout = setTimeout(pollStep, 1500);
        return;
      }

      this._isRequestingStatus = true;

      app.request({
        url: `${app.globalData.baseURL}/api/task-status/${taskId}`,
        method: 'GET',
        success: (res) => {
          // 如果响应返回时任务已被处理终结，直接丢弃该次响应
          if (this._isTaskFinalized || this._pollingTaskId !== taskId) return;

          if (res.data && res.data.data) {
            const tInfo = res.data.data;

            if (tInfo.status === 'completed') {
              // 【核心修复】：瞬间加锁！确保整个生命周期只执行一次成功交付与单次Toast
              this._isTaskFinalized = true;
              if (this.smoothTimer) {
                clearInterval(this.smoothTimer);
                this.smoothTimer = null;
              }
              if (this.pollTimeout) {
                clearTimeout(this.pollTimeout);
                this.pollTimeout = null;
              }
              wx.removeStorageSync('active_meme_task');

              const gifPath = tInfo.data.gif_url;
              const stats = tInfo.data.stats || {};
              const fullGifUrl = app.toAbsoluteUrl(gifPath);

              // 一次性渲染完成状态，进入图片加载阶段，待正常展示后再发提示通知
              this.setData({
                isGenerating: false,
                gifResultUrl: fullGifUrl,
                gifLoaded: false,
                gifWarning: stats.warning || '',
                progress: 100,
                stageText: '动图渲染就绪，正在呈现...'
              });
              return;
            } else if (tInfo.status === 'failed') {
              this._isTaskFinalized = true;
              if (this.smoothTimer) {
                clearInterval(this.smoothTimer);
                this.smoothTimer = null;
              }
              if (this.pollTimeout) {
                clearTimeout(this.pollTimeout);
                this.pollTimeout = null;
              }
              wx.removeStorageSync('active_meme_task');
              this.handleGenerateError(tInfo.error || "生成异常");
              return;
            } else {
              // 仍处于处理中，更新状态文本，保持平滑递增的拟合进度
              const svrProgress = tInfo.progress || 10;
              const updateData = {
                stageText: tInfo.stage_text || this.data.stageText
              };
              if (svrProgress > this.data.progress) {
                updateData.progress = svrProgress;
              }
              if (tInfo.estimated_duration && !this.data.estimatedSeconds) {
                updateData.estimatedSeconds = Math.round(tInfo.estimated_duration);
              }
              this.setData(updateData);
            }
          }
        },
        fail: () => {
          // 网络抖动不打断
        },
        complete: () => {
          this._isRequestingStatus = false;
          // 仅当未终结且仍在生成时，串行排期下一次轮询
          if (!this._isTaskFinalized && this.data.isGenerating && this._pollingTaskId === taskId) {
            this.pollTimeout = setTimeout(pollStep, 1500);
          }
        }
      });
    };

    // 1秒后启动串行轮询
    this.pollTimeout = setTimeout(pollStep, 1000);
  },

  handleGenerateError(msg) {
    this._isTaskFinalized = true;
    if (this.smoothTimer) {
      clearInterval(this.smoothTimer);
      this.smoothTimer = null;
    }
    if (this.pollTimeout) {
      clearTimeout(this.pollTimeout);
      this.pollTimeout = null;
    }
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
    wx.removeStorageSync('active_meme_task');
    this.setData({ isGenerating: false });
    wx.showModal({
      title: '制作提示',
      content: msg || '制作任务响应超时，已为您自动返还制作额度！',
      showCancel: false
    });
    this.updateQuotaInfo();
  },

  onGifLoaded() {
    this.setData({ gifLoaded: true });
    // 动图已在前端界面正常显示，且随时可点击保存相册，此时发出完成提示
    wx.showToast({ 
      title: '制作完成，可保存相册！', 
      icon: 'success', 
      duration: 2500 
    });
  },

  onGifLoadError() {
    this.setData({ gifLoaded: true });
    wx.showToast({ 
      title: '动图就绪，可直接保存相册', 
      icon: 'none', 
      duration: 2200 
    });
  },

  previewGifResult(e) {
    const url = e.currentTarget.dataset.url || this.data.gifResultUrl;
    if (!url) return;
    wx.previewImage({ urls: [url], current: url });
  },

  // --- 保存相册 ---
  saveGifToAlbum() {
    if (!this.data.gifResultUrl) return;
    wx.showLoading({ title: '正在下载动图...' });
    wx.downloadFile({
      url: this.data.gifResultUrl,
      success: (res) => {
        wx.hideLoading();
        if (res.tempFilePath) {
          wx.saveImageToPhotosAlbum({
            filePath: res.tempFilePath,
            success: () => {
              wx.showToast({ title: '已保存至手机相册！', icon: 'success' });
            },
            fail: () => {
              wx.showToast({ title: '保存失败，请授权相册写入权限', icon: 'none' });
            }
          });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '下载失败', icon: 'none' });
      }
    });
  },

  // --- 存入表情合集 (支持自动建默认合集与秒级存入) ---
  openAddToCollection() {
    if (!this.data.gifResultUrl) return;
    const openid = app.globalData.openid || wx.getStorageSync('openid');
    if (!openid) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }

    wx.showLoading({ title: '正在存入合集...' });

    const doSave = (colId, colTitle) => {
      app.request({
        url: `${app.globalData.baseURL}/api/collection/add-item`,
        method: 'POST',
        data: {
          collection_id: colId,
          gif_url: this.data.gifResultUrl,
          title: this.data.caption || '动图表情'
        },
        success: (sRes) => {
          wx.hideLoading();
          if (sRes.data && sRes.data.success) {
            this.setData({ showCollectionModal: false });
            wx.showModal({
              title: '存入成功 🎉',
              content: `已成功存入表情合集【${colTitle}】！\n随时可在底栏【表情合集】或【个人中心】中查看与批量分享。`,
              confirmText: '前往查看',
              cancelText: '留在本页',
              success: (mRes) => {
                if (mRes.confirm) {
                  wx.switchTab({ url: '/pages/collection/collection' });
                }
              }
            });
          } else {
            wx.showToast({ title: (sRes.data && sRes.data.detail) || '存入失败', icon: 'none' });
          }
        },
        fail: () => {
          wx.hideLoading();
          wx.showToast({ title: '网络异常，存入失败', icon: 'none' });
        }
      });
    };

    app.request({
      url: `${app.globalData.baseURL}/api/collection/my?openid=${openid}`,
      method: 'GET',
      success: (res) => {
        let cols = (res.data && res.data.data) || [];
        if (cols.length === 0) {
          // 首次使用自动创建“我的精选表情”默认合集并直接存入
          app.request({
            url: `${app.globalData.baseURL}/api/collection/create`,
            method: 'POST',
            data: {
              openid: openid,
              title: '我的精选表情',
              description: '专属默认表情包收纳抽屉'
            },
            success: (cRes) => {
              if (cRes.data && cRes.data.data) {
                const defaultCol = cRes.data.data;
                this.setData({
                  userCollections: [defaultCol],
                  selectedColId: defaultCol.collection_id
                });
                doSave(defaultCol.collection_id, defaultCol.title || '我的精选表情');
              } else {
                wx.hideLoading();
                wx.showToast({ title: '创建默认合集失败', icon: 'none' });
              }
            },
            fail: () => {
              wx.hideLoading();
              wx.showToast({ title: '网络连接超时', icon: 'none' });
            }
          });
        } else if (cols.length === 1) {
          // 仅有1个合集时直接秒存入，并弹窗提示
          this.setData({
            userCollections: cols,
            selectedColId: cols[0].collection_id
          });
          doSave(cols[0].collection_id, cols[0].title);
        } else {
          // 拥有多个合集时，打开选择浮层供挑选
          wx.hideLoading();
          this.setData({
            userCollections: cols,
            selectedColId: cols[0].collection_id,
            showCollectionModal: true
          });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '网络连接异常', icon: 'none' });
      }
    });
  },

  selectCollection(e) {
    const id = e.currentTarget.dataset.id;
    this.setData({ selectedColId: id });
  },

  closeCollectionModal() {
    this.setData({ showCollectionModal: false });
  },

  onInputNewColTitle(e) {
    this.setData({ newColTitle: e.detail.value });
  },

  createNewColAndSelect() {
    const title = (this.data.newColTitle || '').trim();
    if (!title) {
      wx.showToast({ title: '请输入合集名称', icon: 'none' });
      return;
    }
    const openid = app.globalData.openid || wx.getStorageSync('openid');
    wx.showLoading({ title: '正在创建...' });
    app.request({
      url: `${app.globalData.baseURL}/api/collection/create`,
      method: 'POST',
      data: {
        openid: openid,
        title: title,
        description: '自建表情合集'
      },
      success: (res) => {
        wx.hideLoading();
        if (res.data && res.data.data) {
          const newCol = res.data.data;
          const list = [newCol, ...this.data.userCollections];
          this.setData({
            userCollections: list,
            selectedColId: newCol.collection_id,
            newColTitle: ''
          });
          wx.showToast({ title: '新建成功并已选中', icon: 'success' });
        }
      },
      fail: () => {
        wx.hideLoading();
      }
    });
  },

  confirmSaveToCollection() {
    const colId = this.data.selectedColId;
    if (!colId) {
      wx.showToast({ title: '请选择或新建一个合集', icon: 'none' });
      return;
    }
    wx.showLoading({ title: '正在存入...' });
    app.request({
      url: `${app.globalData.baseURL}/api/collection/add-item`,
      method: 'POST',
      data: {
        collection_id: colId,
        gif_url: this.data.gifResultUrl,
        title: this.data.caption || '动图表情'
      },
      success: (res) => {
        wx.hideLoading();
        if (res.data && res.data.success) {
          this.setData({ showCollectionModal: false });
          const targetCol = this.data.userCollections.find(c => c.collection_id === colId);
          const colName = targetCol ? targetCol.title : '合集';
          wx.showModal({
            title: '存入成功 🎉',
            content: `已成功收入【${colName}】！可在底栏【表情合集】中查看或分享给微信好友。`,
            confirmText: '前往查看',
            cancelText: '留在本页',
            success: (mRes) => {
              if (mRes.confirm) {
                wx.switchTab({ url: '/pages/collection/collection' });
              }
            }
          });
        } else {
          wx.showToast({ title: (res.data && res.data.detail) || '存入失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '网络异常', icon: 'none' });
      }
    });
  },

  handleCheckin() {
    if (!app.globalData.openid) return;
    app.request({
      url: `${app.globalData.baseURL}/api/user/checkin`,
      method: 'POST',
      data: { openid: app.globalData.openid },
      success: (res) => {
        if (res.data && res.data.success) {
          wx.showToast({ title: '签到成功 +3 次！', icon: 'success' });
          this.updateQuotaInfo();
        } else {
          wx.showToast({ title: res.data.error || '今日已签到', icon: 'none' });
        }
      }
    });
  },

  goToRecharge() {
    app.invokeVirtualPayment('meme_100', () => {
      this.updateQuotaInfo();
    });
  },

  dismissFavoriteTip() {
    this.setData({ showFavoriteTip: false });
    wx.setStorageSync('dismiss_fav_tip', true);
  },

  showFavoriteTutorial() {
    wx.showModal({
      title: '添加到我的小程序 ⭐',
      content: '点击右上角「···」按钮，选择「添加到我的小程序」或「添加到桌面」，聊天时直接快捷发图！',
      showCancel: false,
      confirmText: '我知道了'
    });
  },

  stopBubble() {},

  preventTouchMove() {
    // 拦截全屏涂鸦与遮罩层的页面滚动穿透
    return false;
  },

  onUnload() {
    this._isTaskFinalized = true;
    if (this.smoothTimer) {
      clearInterval(this.smoothTimer);
      this.smoothTimer = null;
    }
    if (this.pollTimeout) {
      clearTimeout(this.pollTimeout);
      this.pollTimeout = null;
    }
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  },

  // --- 微信社交裂变分享 ---
  onShareAppMessage(options) {
    const user = (app.globalData && app.globalData.userInfo) || {};
    const inviteCode = user.invite_code || app.globalData.inviterCode || '';
    
    // 如果当前已有生成好的动图，卡片直出动图封面并携带 share_gif 与 share_title 参数，好友点击后直达动图成品
    if (this.data.gifResultUrl) {
      const titleTag = this.data.caption || this.data.selectedTemplateTitle || '专属';
      // 直接携带已经发布的成品地址；新作品通常来自 R2，避免好友再次拼接旧的
      // /outputs 路径后看不到成品。share_task 仍由 onLoad 保留，用于兼容旧分享卡片。
      const taskQuery = `&share_gif=${encodeURIComponent(this.data.gifResultUrl)}`;
      return {
        title: `🔥 快接招！我刚用 AI 做了【${titleTag}】表情包，快来看看！`,
        path: `/pages/index/index?inviter=${encodeURIComponent(inviteCode)}${taskQuery}&share_title=${encodeURIComponent(titleTag)}&ref_tpl=${encodeURIComponent(this.data.selectedTemplate)}`,
        imageUrl: this.data.gifResultUrl
      };
    }

    // 默认首页分享
    return {
      title: '送你 10 次免费动图制作额度，一键生成微信专属表情包！',
      path: `/pages/index/index?inviter=${encodeURIComponent(inviteCode)}`
    };
  },

  onShareTimeline() {
    const titleTag = this.data.caption || this.data.selectedTemplateTitle || 'AI专属表情包';
    return {
      title: `我用 AI 做了【${titleTag}】动态表情包，一键定制超好玩！`,
      query: this.data.gifResultUrl
        ? `share_gif=${encodeURIComponent(this.data.gifResultUrl)}&share_title=${encodeURIComponent(titleTag)}&ref_tpl=${encodeURIComponent(this.data.selectedTemplate)}`
        : `ref_tpl=${encodeURIComponent(this.data.selectedTemplate)}`,
      imageUrl: this.data.gifResultUrl || ''
    };
  }
});
