const app = getApp();

Page({
  data: {
    refImagePath: '',
    textMode: 'none', // 'none' (纯表情) | 'auto' (预设场景) | 'custom' (自定义台词)
    selectedTheme: 'worker',
    customTexts: '',
    composition: 'bust', // 'bust' (半身手势) | 'closeup' (大头微表情)
    selectedStyle: 'wechat_sticker',
    customStyleText: '',
    characterDesc: '',

    themePackages: [
      { id: 'worker', name: '💼 打工人日常', desc: '好的收到/改稿中/搬砖/谢老板', icon: '💼' },
      { id: 'battle', name: '⚡ 群聊斗图', desc: '问号脸/退退退/头秃/就这', icon: '⚡' },
      { id: 'cute', name: '💖 萌系可爱', desc: '笔芯/抱抱/委屈/萌萌哒', icon: '💖' },
      { id: 'slack', name: '🍵 摆烂躺平', desc: '开摆/随便吧/无所谓/看热闹', icon: '🍵' },
      { id: 'daily', name: '💬 日常高频', desc: 'OK/点赞/摸鱼中/干饭啦', icon: '💬' }
    ],

    stylePresets: [
      { id: 'wechat_sticker', name: '✨ 经典手绘贴纸', desc: '2D Q版扁平手绘 · 微信原生质感' },
      { id: 'cute_chibi', name: '🐱 Q版萌系大眼', desc: '超甜圆润萌化感 · 活泼可爱' },
      { id: 'funny_line', name: '✏️ 魔性沙雕线描', desc: '黑白搞怪线稿 · 斗图神作' },
      { id: '3d_toy', name: '🧸 3D 公仔潮玩', desc: '立体盲盒潮玩 · 饱满光泽' },
      { id: 'custom', name: '🎨 自定义画风...', desc: '手动输入任何专属画风关键词' }
    ],

    // 弹窗状态
    showModal: false,
    isGenerating: false,
    hasCompletedTask: false,
    currentStep: 1,
    progress: 5,
    stageTitle: '阶段 1/4: 分析角色视觉特征...',
    elapsedSeconds: 0,
    estimatedTotalSeconds: 32,

    // 16 宫格结果
    taskId: '',
    stickersList: [],
    selectedCount: 16,
    isAllSelected: true,

    // 大图预览
    showLargePreview: false,
    largePreviewIndex: 0
  },

  _timer: null,
  _pollTimer: null,

  onLoad(options) {
    if (options && options.refUrl) {
      const url = decodeURIComponent(options.refUrl);
      this.setData({ refImagePath: url });
      wx.showToast({ title: '已载入素材图片', icon: 'none' });
    }
    this.restoreCachedResult();
  },

  onUnload() {
    this.clearTimers();
  },

  clearTimers() {
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
  },

  restoreCachedResult() {
    const cached = wx.getStorageSync('cache_sticker16_result');
    if (cached && cached.stickersList && cached.stickersList.length === 16) {
      this.setData({
        hasCompletedTask: true,
        stickersList: cached.stickersList,
        selectedCount: cached.stickersList.filter(s => s.selected).length,
        taskId: cached.taskId || ''
      });
    }
  },

  // 选择参考图片 (相册/拍照)
  chooseImage() {
    const that = this;
    if (wx.chooseMedia) {
      wx.chooseMedia({
        count: 1,
        mediaType: ['image'],
        sourceType: ['album', 'camera'],
        success: (res) => {
          if (res.tempFiles && res.tempFiles.length > 0) {
            that.processSelectedImage(res.tempFiles[0].tempFilePath);
          }
        }
      });
    } else {
      wx.chooseImage({
        count: 1,
        sourceType: ['album', 'camera'],
        success: (res) => {
          if (res.tempFilePaths && res.tempFilePaths.length > 0) {
            that.processSelectedImage(res.tempFilePaths[0]);
          }
        }
      });
    }
  },

  async processSelectedImage(filePath) {
    // 微信内容安全合规审查
    if (app.checkImageSecurity) {
      const isSafe = await app.checkImageSecurity(filePath);
      if (!isSafe) return;
    }
    this.setData({ refImagePath: filePath });
    wx.showToast({ title: '已添加参考图', icon: 'success' });
  },

  clearImage() {
    this.setData({ refImagePath: '' });
  },

  previewRefImage() {
    if (this.data.refImagePath) {
      wx.previewImage({ urls: [this.data.refImagePath] });
    }
  },

  selectTextMode(e) {
    this.setData({ textMode: e.currentTarget.dataset.mode });
  },

  selectTheme(e) {
    this.setData({ selectedTheme: e.currentTarget.dataset.id });
  },

  onInputCustomTexts(e) {
    this.setData({ customTexts: e.detail.value });
  },

  selectComposition(e) {
    this.setData({ composition: e.currentTarget.dataset.comp });
  },

  selectStyle(e) {
    this.setData({ selectedStyle: e.currentTarget.dataset.id });
  },

  onInputCustomStyle(e) {
    this.setData({ customStyleText: e.detail.value });
  },

  onInputDesc(e) {
    this.setData({ characterDesc: e.detail.value });
  },

  preventBubble() {},
  preventScroll() {},

  onStickerImageError(e) {
    const idx = e.currentTarget.dataset.index;
    console.warn(`Sticker ${idx} failed to load, falling back`, e);
    const list = this.data.stickersList;
    if (list[idx] && list[idx].url && list[idx].displayUrl !== list[idx].url) {
      list[idx].displayUrl = list[idx].url;
      this.setData({ stickersList: list });
    }
  },

  // ==================== 启动制作 16 款表情 ====================
  async startMakeStickers() {
    if (!this.data.refImagePath) {
      wx.showModal({
        title: '提示',
        content: '请先上传一张参考图片（可自拍、生活照、萌宠或从素材库保存的表情）',
        showCancel: false,
        confirmText: '去上传',
        confirmColor: '#07c160'
      });
      return;
    }

    // 文本内容安全校验
    const textsToCheck = [this.data.characterDesc];
    if (this.data.textMode === 'custom' && this.data.customTexts) {
      textsToCheck.push(this.data.customTexts);
    }
    if (this.data.selectedStyle === 'custom' && this.data.customStyleText) {
      textsToCheck.push(this.data.customStyleText);
    }

    for (let txt of textsToCheck) {
      if (txt && app.checkTextSecurity) {
        const isSafe = await app.checkTextSecurity(txt);
        if (!isSafe) return;
      }
    }

    // 检查并准备本地临时文件
    let localFilePath = this.data.refImagePath;
    if (/^https?:\/\//i.test(localFilePath)) {
      wx.showLoading({ title: '正在下载素材...', mask: true });
      try {
        const downloadRes = await new Promise((resolve, reject) => {
          wx.downloadFile({
            url: localFilePath,
            success: resolve,
            fail: reject
          });
        });
        wx.hideLoading();
        if (downloadRes.statusCode === 200) {
          localFilePath = downloadRes.tempFilePath;
        } else {
          throw new Error('素材下载失败');
        }
      } catch (err) {
        wx.hideLoading();
        wx.showToast({ title: '图片下载失败，请从相册重选', icon: 'none' });
        return;
      }
    }

    // 打开弹窗，开启进度计时
    this.setData({
      showModal: true,
      isGenerating: true,
      currentStep: 1,
      progress: 8,
      stageTitle: '阶段 1/4: 提取角色视觉特征...',
      elapsedSeconds: 0
    });

    this.startProgressTicker();

    // 组装参数
    let finalTheme = 'none';
    let customTextsParam = '';

    if (this.data.textMode === 'none') {
      finalTheme = 'none';
    } else if (this.data.textMode === 'auto') {
      finalTheme = this.data.selectedTheme;
    } else if (this.data.textMode === 'custom') {
      finalTheme = 'custom';
      const lines = (this.data.customTexts || '').split('\n').map(s => s.trim()).filter(Boolean);
      if (lines.length > 0) {
        customTextsParam = JSON.stringify(lines);
      }
    }

    let finalStyle = this.data.selectedStyle;
    if (this.data.selectedStyle === 'custom' && this.data.customStyleText.trim()) {
      finalStyle = this.data.customStyleText.trim();
    }

    const openid = app.globalData.openid || wx.getStorageSync('openid') || '';
    const uploadUrl = `${app.globalData.baseURL}/api/generate-async`;

    const formData = {
      output_mode: 'sticker16',
      text_package: finalTheme,
      style_preset: finalStyle,
      composition_preset: this.data.composition,
      character_desc: this.data.characterDesc || '',
      bg_preset: 'white',
      openid: openid
    };
    if (customTextsParam) {
      formData.custom_texts = customTextsParam;
    }

    app.uploadFile({
      url: uploadUrl,
      filePath: localFilePath,
      name: 'ref_image',
      formData: formData,
      success: (res) => {
        let respData = null;
        try {
          respData = JSON.parse(res.data);
        } catch (e) {
          console.error('Parse response failed:', res.data);
        }

        if (res.statusCode === 200 && respData && respData.code === 0) {
          const taskId = respData.data.task_id;
          this.setData({ taskId: taskId, currentStep: 2 });
          this.startPollingTask(taskId);
        } else {
          let msg = (respData && respData.detail) || '服务开小差了，请稍后重试';
          this.handleGenerateFailed(msg);
        }
      },
      fail: (err) => {
        console.error('Upload failed:', err);
        this.handleGenerateFailed('网络连接超时，请重试');
      }
    });
  },

  // 平滑计时器
  startProgressTicker() {
    this.clearTimers();
    let sec = 0;
    const estimated = 32;

    this._timer = setInterval(() => {
      sec++;
      let pct = Math.min(94, Math.floor(8 + (sec / estimated) * 86));
      let step = 1;
      let stage = '阶段 1/4: 提取角色视觉特征...';

      if (sec >= 5 && sec < 18) {
        step = 2;
        stage = '阶段 2/4: 绘制 16 帧分镜生动表情...';
      } else if (sec >= 18) {
        step = 3;
        stage = '阶段 3/4: 矩阵网格微调与对齐...';
      }

      this.setData({
        elapsedSeconds: sec,
        progress: pct,
        currentStep: step,
        stageTitle: stage
      });
    }, 1000);
  },

  // 轮询任务状态
  startPollingTask(taskId) {
    let pollCount = 0;
    this._pollTimer = setInterval(() => {
      pollCount++;
      app.request({
        url: `${app.globalData.baseURL}/api/task-status/${taskId}`,
        method: 'GET',
        success: (res) => {
          if (res.statusCode === 200 && res.data && res.data.code === 0) {
            const task = res.data.data;
            if (task.status === 'completed' || task.status === 'success') {
              this.handleGenerateSuccess(task);
            } else if (task.status === 'failed') {
              this.handleGenerateFailed(task.error || '生成遇到问题，额度已返还');
            }
          }
        }
      });
    }, 2000);
  },

  // 生成成功处理
  handleGenerateSuccess(taskData) {
    this.clearTimers();
    const result = taskData.data || taskData;
    const rawItems = result.stickers || result.frames || [];

    const formattedList = rawItems.map((item, idx) => {
      let rawUrl = '';
      let standardUrl = '';
      let text = '';
      if (typeof item === 'string') {
        standardUrl = app.toAbsoluteUrl(item);
        rawUrl = standardUrl;
      } else {
        standardUrl = app.toAbsoluteUrl(item.url || '');
        rawUrl = app.toAbsoluteUrl(item.raw_url || item.url || '');
        text = item.caption || item.text || '';
      }

      const displayUrl = (this.data.textMode === 'none' ? (rawUrl || standardUrl) : (standardUrl || rawUrl));

      return {
        id: `sticker_${idx + 1}`,
        index: idx,
        url: standardUrl,
        rawUrl: rawUrl,
        displayUrl: displayUrl,
        text: text,
        selected: true
      };
    });

    this.setData({
      isGenerating: false,
      hasCompletedTask: true,
      currentStep: 4,
      progress: 100,
      stageTitle: '阶段 4/4: 制作完成！',
      stickersList: formattedList,
      selectedCount: formattedList.length,
      isAllSelected: true
    });

    wx.setStorageSync('cache_sticker16_result', {
      taskId: this.data.taskId,
      stickersList: formattedList,
      time: Date.now()
    });

    wx.showToast({ title: '16 款表情制作完成！', icon: 'success' });
  },

  handleGenerateFailed(errorMsg) {
    this.clearTimers();
    this.setData({ isGenerating: false });
    wx.showModal({
      title: '制作未完成',
      content: errorMsg || '生图遇到问题，额度已自动返还。',
      showCancel: false,
      confirmText: '我知道了'
    });
  },

  closeModal() {
    this.setData({ showModal: false });
  },

  openResultModal() {
    this.setData({ showModal: true });
  },

  // 勾选/取消单张表情
  toggleSelectSticker(e) {
    const idx = e.currentTarget.dataset.index;
    const list = this.data.stickersList;
    list[idx].selected = !list[idx].selected;
    const count = list.filter(s => s.selected).length;
    this.setData({
      stickersList: list,
      selectedCount: count,
      isAllSelected: count === list.length
    });
  },

  // 全选/反选
  toggleSelectAll() {
    const nextState = !this.data.isAllSelected;
    const list = this.data.stickersList.map(s => ({ ...s, selected: nextState }));
    this.setData({
      stickersList: list,
      selectedCount: nextState ? list.length : 0,
      isAllSelected: nextState
    });
  },

  // 大图查看
  viewStickerLarge(e) {
    const idx = e.currentTarget.dataset.index;
    this.setData({
      showLargePreview: true,
      largePreviewIndex: idx
    });
  },

  closeLargePreview() {
    this.setData({ showLargePreview: false });
  },

  // 保存单张表情到相册
  async saveSingleStickerToAlbum() {
    const sticker = this.data.stickersList[this.data.largePreviewIndex];
    if (!sticker) return;
    wx.showLoading({ title: '正在保存...', mask: true });
    try {
      await this.downloadAndSaveToAlbum(sticker.displayUrl);
      wx.hideLoading();
      wx.showToast({ title: '已保存至系统相册', icon: 'success' });
      this.closeLargePreview();
    } catch (e) {
      wx.hideLoading();
      this.handleAlbumAuthError(e);
    }
  },

  // 批量保存选中的表情到手机相册
  async saveSelectedStickersToAlbum() {
    const selectedStickers = this.data.stickersList.filter(s => s.selected);
    if (selectedStickers.length === 0) {
      wx.showToast({ title: '请先勾选表情', icon: 'none' });
      return;
    }

    wx.showLoading({ title: `正在保存 (0/${selectedStickers.length})...`, mask: true });
    let savedCount = 0;

    for (let i = 0; i < selectedStickers.length; i++) {
      try {
        wx.showLoading({ title: `正在保存 (${i + 1}/${selectedStickers.length})...`, mask: true });
        await this.downloadAndSaveToAlbum(selectedStickers[i].displayUrl);
        savedCount++;
      } catch (err) {
        console.warn('Save sticker failed:', err);
        wx.hideLoading();
        this.handleAlbumAuthError(err);
        return;
      }
    }

    wx.hideLoading();
    wx.showToast({ title: `已成功保存 ${savedCount} 款表情！`, icon: 'success', duration: 2000 });
  },

  // 保存到手机相册工具方法
  downloadAndSaveToAlbum(url) {
    return new Promise((resolve, reject) => {
      wx.downloadFile({
        url: url,
        success: (res) => {
          if (res.statusCode === 200 && res.tempFilePath) {
            wx.saveImageToPhotosAlbum({
              filePath: res.tempFilePath,
              success: resolve,
              fail: reject
            });
          } else {
            reject(new Error('下载图片失败'));
          }
        },
        fail: reject
      });
    });
  },

  handleAlbumAuthError(err) {
    if (err && err.errMsg && err.errMsg.indexOf('auth') !== -1) {
      wx.showModal({
        title: '需要相册权限',
        content: '保存表情需要允许保存到系统相册，请前往设置开启权限。',
        confirmText: '去开启',
        confirmColor: '#07c160',
        success: (m) => {
          if (m.confirm) wx.openSetting();
        }
      });
    } else {
      wx.showToast({ title: '保存失败，请检查网络或重试', icon: 'none' });
    }
  },

  // 存入合集
  saveToMyCollection() {
    const firstSticker = this.data.stickersList[0];
    if (!firstSticker) return;
    wx.navigateTo({
      url: `/pages/collection/collection?add_gif=${encodeURIComponent(firstSticker.displayUrl)}`
    });
  }
});
