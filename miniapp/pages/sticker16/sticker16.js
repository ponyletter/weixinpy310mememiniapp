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
    customTextsPlaceholder: '收到\n好的老板\n疯狂搬砖\n摸鱼中\n头秃了\n我太难了\n别催了\n下班溜了\n血压上来了\n需求是啥\n搞定收工\n夸得我脸红\n跪求别催\n吃瓜看戏\n困到变形\n告辞溜了',

    themePackages: [
      {
        id: 'none',
        name: '无字纯表情',
        desc: '纯净无字·自由发挥自由斗图',
        icon: '🈳',
        tag: '推荐',
        texts: []
      },
      {
        id: 'worker',
        name: '打工人日常',
        desc: '职场生存必备·好的收到/疯狂搬砖',
        icon: '💼',
        tag: '热门',
        texts: ['收到', '好的老板', '疯狂搬砖', '摸鱼中', '头秃了', '我太难了', '方案又改了', '震惊老铁', '血压上来了', '需求是什么', '搞定收工', '夸得我脸红', '跪求别催', '吃瓜看戏', '困到变形', '我下班啦溜了']
      },
      {
        id: 'battle',
        name: '群聊斗图',
        desc: '轻松拿捏全场·点赞666/问号脸/吃瓜',
        icon: '⚡',
        tag: '斗图神作',
        texts: ['点赞666', '得瑟拿捏', '疯狂输出', '暗中观察', '裂开崩溃', '猛男落泪', '出来挨打', '惊呆了', '无语翻白眼', '满头问号', '帅气登场', '害羞掩面', '抱拳感谢', '现场吃瓜', '睡了别艾特', '告辞溜了']
      },
      {
        id: 'cute',
        name: '萌系可爱',
        desc: '聊天更甜·谢谢你/么么哒/求抱抱',
        icon: '💖',
        tag: '治愈甜系',
        texts: ['谢谢你', '么么哒', '加油鸭', '喝杯奶茶', '委屈巴巴', '求抱抱', '生气气了', '星星眼哇塞', '叹气气', '疑惑脸??', '酷酷的哦', '爱你哟', '拜托拜托', '干杯耶', '呼呼大睡', '飞奔向你']
      },
      {
        id: 'slack',
        name: '摆烂躺平',
        desc: '佛系佛系·随缘吧/我装的/毫无波澜',
        icon: '🍵',
        tag: '佛系',
        texts: ['好的(假装积极)', '随缘吧', '我装的', '看神仙打架', '毁灭吧', '哭死扎心', '勿扰已死', '还能这样', '累了退下吧', '听不懂不想懂', '佛系看淡', '算了吧', '放过我吧', '毫无波澜', '躺平中', '彻底告辞']
      },
      {
        id: 'daily',
        name: '日常高频',
        desc: '社交通用·OK没问题/比心心/冲鸭',
        icon: '💬',
        tag: '常用',
        texts: ['OK没问题', '比心心', '冲鸭', '干饭干饭', '自闭了', '抱头痛哭', '气死我了', '吓我一跳', '无所谓', '你认真的吗', '暗中自嗨', '不好意思啦', '求求了', '坐等好戏', '好困啊', '撤退撤退']
      },
      {
        id: 'couple',
        name: '情侣撒娇',
        desc: '甜宠日常·想你啦/亲亲/哼生气了',
        icon: '👩‍❤️‍👨',
        tag: '情侣互动',
        texts: ['想你啦', '亲亲一个', '在忙什么呀', '给你送爱心', '哼不理你了', '委屈哭唧唧', '气鼓鼓', '哇你好帅', '叹气想抱抱', '又在想谁呢', '今天超酷', '脸红害羞', '求抱抱嘛', '监督你干饭', '想和你贴贴', '飞奔奔向你']
      },
      {
        id: 'memes',
        name: '网络热梗',
        desc: '魔性搞笑·泰裤辣/尊嘟假嘟/退退退',
        icon: '🔥',
        tag: '爆笑魔性',
        texts: ['泰裤辣', '泰棒了比心', '疯狂敲碗', '优雅永不过时', '破大防了', '小丑竟是我', '尊嘟假嘟', '绝了绝了', '退退退', 'CPU烧了', '赢麻了', '偷笑不敢看', 'V我50', '吃瓜一线', '困到起飞', '扛着火车跑']
      },
      {
        id: 'social',
        name: '礼貌社交',
        desc: '客气体面·辛苦老师啦/收到感谢/拜托',
        icon: '🤝',
        tag: '客气体面',
        texts: ['辛苦老师啦', '收到感谢', '马上安排', '给您倒杯茶', '实在抱歉', '感激涕零', '非常理解', '万分感谢', '让您见笑了', '请教一下', '祝您顺利', '受宠若惊', '拜托您啦', '围观学习', '不打扰您休息', '回聊祝顺']
      },
      {
        id: 'pet_mood',
        name: '萌宠心声',
        desc: '毛孩子专属·开饭啦/猫猫流泪/求摸头',
        icon: '🐾',
        tag: '萌宠专属',
        texts: ['开饭啦干饭', '歪头卖萌', '疯狂拆家', '给口吃的吧', '狗带了', '猫猫流泪', '哈士奇狂怒', '吓掉猫毛', '猫猫鄙视', '狗头问号', '霸气小猫', '舔舔小爪', '求摸下巴', '看两脚兽打架', '呼噜呼噜', '撒欢开跑']
      },
      {
        id: 'custom',
        name: '自定义16句台词',
        desc: '自由逐行编辑 16 句个性台词',
        icon: '✏️',
        tag: '自由定制',
        texts: []
      }
    ],

    stylePresets: [
      { id: 'wechat_sticker', icon: '✨', name: '经典手绘', desc: '2D扁平·原生贴纸感', tag: '经典' },
      { id: 'real_person', icon: '📸', name: '写实真人', desc: '真实摄影·生动人像还原', tag: '热门' },
      { id: 'cute_chibi', icon: '🐱', name: 'Q版萌系', desc: '圆润大眼·治愈可爱', tag: '治愈' },
      { id: 'funny_line', icon: '✏️', name: '沙雕线描', desc: '黑白线稿·斗图神作', tag: '魔性' },
      { id: '3d_toy', icon: '🧸', name: '3D公仔', desc: '立体潮玩·盲盒质感', tag: '潮玩' },
      { id: 'custom', icon: '🎨', name: '自定义画风', desc: '输入专属提示词', tag: '自由' }
    ],

    // 弹窗与折叠抽屉状态
    showStyleDrawer: false,
    showThemeDrawer: false,
    showDescInput: false,
    showInlineTextsPreview: false,
    activeDrawerThemeId: 'worker',
    activeDrawerThemeObj: null,
    currentStyleObj: null,
    currentThemeObj: null,

    // 运行与展示状态
    showModal: false,
    isGenerating: false,
    hasCompletedTask: false,
    currentStep: 1,
    progress: 5,
    stageTitle: '阶段 1/4: 提取角色视觉特征...',
    elapsedSeconds: 0,
    estimatedSeconds: 60,

    // 16 宫格结果
    taskId: '',
    stickersList: [],
    selectedCount: 16,
    isAllSelected: true,

    // 大图预览
    showLargePreview: false,
    largePreviewIndex: 0,

    // 存入合集弹窗
    showCollectionModal: false,
    loadingCollections: false,
    userCollections: [],
    showCreateInput: false,
    newCollectionTitle: '',
    isSavingBatch: false
  },

  _timer: null,
  _pollTimer: null,

  onLoad(options) {
    const defaultStyle = this.data.stylePresets.find(s => s.id === this.data.selectedStyle) || this.data.stylePresets[0];
    const defaultTheme = this.data.themePackages.find(t => t.id === this.data.textMode) || this.data.themePackages[0];
    this.setData({
      currentStyleObj: defaultStyle,
      currentThemeObj: defaultTheme,
      activeDrawerThemeObj: defaultTheme
    });

    if (options && options.refUrl) {
      const url = decodeURIComponent(options.refUrl);
      this.setData({ refImagePath: url });
      wx.showToast({ title: '已载入素材图片', icon: 'none' });
    }
  },

  onShow() {
    this.checkResumeActiveTask();
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

  // 恢复正在进行中的任务或历史完成结果
  checkResumeActiveTask() {
    const activeTask = wx.getStorageSync('active_sticker16_task');
    if (activeTask && activeTask.taskId) {
      const now = Date.now();
      // 15 分钟内的任务有效恢复
      if (now - (activeTask.timestamp || 0) < 15 * 60 * 1000) {
        if (!this.data.isGenerating) {
          const elapsed = Math.max(1, Math.floor((now - activeTask.timestamp) / 1000));
          const est = activeTask.estimatedSeconds || 60;
          let calculatedProgress = 10;
          if (elapsed < est) {
            calculatedProgress = Math.min(92, Math.floor(10 + (elapsed / est) * 82));
          } else {
            calculatedProgress = Math.min(98, 92 + Math.floor((elapsed - est) / 8));
          }

          this.setData({
            isGenerating: true,
            taskId: activeTask.taskId,
            refImagePath: activeTask.refImagePath || this.data.refImagePath,
            textMode: activeTask.textMode || this.data.textMode,
            estimatedSeconds: est,
            elapsedSeconds: elapsed,
            progress: calculatedProgress,
            stageTitle: '正在恢复云端渲染进度...'
          });

          this.startProgressTicker(elapsed);
          this.startPollingTask(activeTask.taskId);

          setTimeout(() => {
            wx.pageScrollTo({
              selector: '#generation-section',
              duration: 300
            });
          }, 250);
        }
        return;
      } else {
        wx.removeStorageSync('active_sticker16_task');
      }
    }

    if (!this.data.isGenerating && (!this.data.stickersList || this.data.stickersList.length === 0)) {
      this.restoreCachedResult();
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

  // --- 画风抽屉交互 ---
  openStyleDrawer() {
    this.setData({ showStyleDrawer: true });
  },

  closeStyleDrawer() {
    this.setData({ showStyleDrawer: false });
  },

  selectStyleFromDrawer(e) {
    const id = e.currentTarget.dataset.id;
    const styleObj = this.data.stylePresets.find(s => s.id === id) || this.data.stylePresets[0];
    this.setData({
      selectedStyle: id,
      currentStyleObj: styleObj
    });
    if (id !== 'custom') {
      this.setData({ showStyleDrawer: false });
    }
  },

  confirmStyleDrawer() {
    this.setData({ showStyleDrawer: false });
  },

  // --- 场景主题与台词抽屉交互 ---
  openThemeDrawer() {
    const curThemeId = this.data.textMode === 'none' ? 'none' : (this.data.textMode === 'custom' ? 'custom' : this.data.selectedTheme);
    const activeObj = this.data.themePackages.find(t => t.id === curThemeId) || this.data.themePackages[0];
    this.setData({
      showThemeDrawer: true,
      activeDrawerThemeId: curThemeId,
      activeDrawerThemeObj: activeObj
    });
  },

  closeThemeDrawer() {
    this.setData({ showThemeDrawer: false });
  },

  selectThemeInDrawer(e) {
    const id = e.currentTarget.dataset.id;
    const activeObj = this.data.themePackages.find(t => t.id === id) || this.data.themePackages[0];
    this.setData({
      activeDrawerThemeId: id,
      activeDrawerThemeObj: activeObj
    });
  },

  confirmThemeChoice(e) {
    const id = (e && e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.id) || this.data.activeDrawerThemeId;
    const themeObj = this.data.themePackages.find(t => t.id === id) || this.data.themePackages[0];
    if (id === 'none') {
      this.setData({
        textMode: 'none',
        selectedTheme: 'none',
        currentThemeObj: themeObj,
        showThemeDrawer: false,
        showInlineTextsPreview: false
      });
    } else if (id === 'custom') {
      this.setData({
        textMode: 'custom',
        selectedTheme: 'custom',
        currentThemeObj: themeObj,
        showThemeDrawer: false
      });
    } else {
      this.setData({
        textMode: 'auto',
        selectedTheme: id,
        currentThemeObj: themeObj,
        showThemeDrawer: false,
        showInlineTextsPreview: false
      });
    }
  },

  switchToCustomFromTheme(e) {
    const themeId = (e && e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.id) || this.data.activeDrawerThemeId || this.data.selectedTheme;
    const themeObj = this.data.themePackages.find(t => t.id === themeId);
    const customStr = (themeObj && themeObj.texts && themeObj.texts.length > 0) ? themeObj.texts.join('\n') : '';
    const customObj = this.data.themePackages.find(t => t.id === 'custom') || this.data.themePackages[this.data.themePackages.length - 1];
    this.setData({
      textMode: 'custom',
      selectedTheme: 'custom',
      customTexts: customStr,
      currentThemeObj: customObj,
      showThemeDrawer: false,
      showInlineTextsPreview: false
    });
    wx.showToast({ title: '已将台词载入自定义输入框', icon: 'none' });
  },

  toggleInlineTextsPreview() {
    this.setData({ showInlineTextsPreview: !this.data.showInlineTextsPreview });
  },

  toggleDescInput() {
    this.setData({ showDescInput: !this.data.showDescInput });
  },

  selectTextMode(e) {
    const mode = e.currentTarget.dataset.mode;
    const themeObj = this.data.themePackages.find(t => t.id === mode) || this.data.currentThemeObj;
    this.setData({
      textMode: mode,
      currentThemeObj: themeObj
    });
  },

  selectTheme(e) {
    const id = e.currentTarget.dataset.id;
    const themeObj = this.data.themePackages.find(t => t.id === id) || this.data.themePackages[0];
    this.setData({
      selectedTheme: id,
      currentThemeObj: themeObj
    });
  },

  onInputCustomTexts(e) {
    this.setData({ customTexts: e.detail.value });
  },

  selectComposition(e) {
    this.setData({ composition: e.currentTarget.dataset.comp });
  },

  selectStyle(e) {
    const id = e.currentTarget.dataset.id;
    const styleObj = this.data.stylePresets.find(s => s.id === id) || this.data.stylePresets[0];
    this.setData({
      selectedStyle: id,
      currentStyleObj: styleObj
    });
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
        confirmColor: '#6c5ce7'
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

    // 开启进度计时并平滑滚动到制作区
    this.setData({
      isGenerating: true,
      currentStep: 1,
      progress: 6,
      stageTitle: '阶段 1/4: 提取角色视觉特征...',
      elapsedSeconds: 0
    });

    this.startProgressTicker(0);

    setTimeout(() => {
      wx.pageScrollTo({
        selector: '#generation-section',
        duration: 400
      });
    }, 150);

    // 组装参数
    let finalTheme = 'none';
    let customTextsParam = '';

    if (this.data.textMode === 'none') {
      finalTheme = 'none';
    } else if (this.data.textMode === 'auto') {
      finalTheme = this.data.selectedTheme;
    } else if (this.data.textMode === 'custom') {
      finalTheme = 'custom';
      const lines = (this.data.customTexts || '')
        .split('\n')
        .map(s => s.trim().replace(/^第\s*\d+\s*[句行号条][:：\s]*/i, ''))
        .filter(Boolean);
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
          const est = (respData.data && respData.data.estimated_duration) ? Math.max(20, Math.round(respData.data.estimated_duration)) : (this.data.estimatedSeconds || 60);

          // 持久化存储活跃任务，退出后返回可无缝恢复
          wx.setStorageSync('active_sticker16_task', {
            taskId: taskId,
            timestamp: Date.now(),
            refImagePath: this.data.refImagePath,
            textMode: this.data.textMode,
            estimatedSeconds: est
          });

          this.setData({ 
            taskId: taskId, 
            currentStep: 2,
            estimatedSeconds: est
          });
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

  // 平滑计时器 (支持断点恢复传入已耗时秒数)
  startProgressTicker(initialSec = 0) {
    this.clearTimers();
    let sec = initialSec;

    this._timer = setInterval(() => {
      sec++;
      const targetSeconds = Math.max(20, this.data.estimatedSeconds || 60);
      let pct = 6;
      if (sec < targetSeconds) {
        pct = Math.min(92, Math.floor(6 + (sec / targetSeconds) * 86));
      } else {
        // 超出预估时间后，平滑爬升到 98%，不冻结
        pct = Math.min(98, 92 + Math.floor((sec - targetSeconds) / 8));
      }

      let step = 1;
      let stage = '阶段 1/4: 提取角色视觉特征...';

      if (sec >= 4 && sec < 18) {
        step = 2;
        stage = '阶段 2/4: 绘制 16 帧分镜生动表情...';
      } else if (sec >= 18) {
        step = 3;
        stage = '阶段 3/4: 矩阵切片与超清对齐...';
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
            if (task.estimated_duration && !this.data.estimatedSeconds) {
              this.setData({ estimatedSeconds: Math.max(20, Math.round(task.estimated_duration)) });
            }
            if (task.stage_text) {
              this.setData({ stageTitle: task.stage_text });
            }
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

    wx.removeStorageSync('active_sticker16_task');
    wx.setStorageSync('cache_sticker16_result', {
      taskId: this.data.taskId,
      stickersList: formattedList,
      time: Date.now()
    });

    wx.showToast({ title: '16 款表情制作完成！', icon: 'success' });
  },

  handleGenerateFailed(errorMsg) {
    this.clearTimers();
    wx.removeStorageSync('active_sticker16_task');
    this.setData({ isGenerating: false });
    wx.showModal({
      title: '制作未完成',
      content: errorMsg || '生图遇到问题，额度已自动返还。',
      showCancel: false,
      confirmText: '我知道了'
    });
  },

  scrollToResult() {
    wx.pageScrollTo({
      selector: '#generation-section',
      duration: 350
    });
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
        confirmColor: '#6c5ce7',
        success: (m) => {
          if (m.confirm) wx.openSetting();
        }
      });
    } else {
      wx.showToast({ title: '保存失败，请检查网络或重试', icon: 'none' });
    }
  },

  // ==================== 存入合集功能 (原地弹窗选择/新建 + 选中的表情批量独立存入) ====================
  // 打开合集选择弹窗
  saveToMyCollection() {
    const selectedStickers = (this.data.stickersList || []).filter(s => s.selected);
    if (!selectedStickers.length) {
      wx.showToast({ title: '请至少勾选 1 款表情', icon: 'none' });
      return;
    }
    this.setData({
      showCollectionModal: true,
      showCreateInput: false,
      newCollectionTitle: ''
    });
    this.fetchUserCollections();
  },

  // 关闭合集弹窗
  closeCollectionModal() {
    this.setData({
      showCollectionModal: false,
      showCreateInput: false
    });
  },

  // 获取用户所有合集列表
  fetchUserCollections() {
    const openid = app.globalData.openid || wx.getStorageSync('openid') || '';
    this.setData({ loadingCollections: true });
    app.request({
      url: `${app.globalData.baseURL}/api/collection/my?openid=${encodeURIComponent(openid)}`,
      method: 'GET',
      success: (res) => {
        if (res.data && res.data.success && Array.isArray(res.data.data)) {
          this.setData({ userCollections: res.data.data });
        }
      },
      fail: () => {
        wx.showToast({ title: '获取合集列表失败', icon: 'none' });
      },
      complete: () => {
        this.setData({ loadingCollections: false });
      }
    });
  },

  // 选择已有合集并存入选中的表情
  chooseCollectionAndSave(e) {
    const colId = e.currentTarget.dataset.id;
    if (!colId) return;
    this.executeBatchSave(colId);
  },

  // 切换新建合集输入框
  toggleCreateInput() {
    this.setData({
      showCreateInput: !this.data.showCreateInput,
      newCollectionTitle: ''
    });
  },

  onNewCollectionTitleInput(e) {
    this.setData({
      newCollectionTitle: e.detail.value
    });
  },

  // 提交新建合集并存入
  submitCreateAndSave() {
    const title = (this.data.newCollectionTitle || '').trim();
    if (!title) {
      wx.showToast({ title: '请输入合集名称', icon: 'none' });
      return;
    }
    const openid = app.globalData.openid || wx.getStorageSync('openid') || '';
    wx.showLoading({ title: '正在创建合集...' });

    app.request({
      url: `${app.globalData.baseURL}/api/collection/create`,
      method: 'POST',
      data: {
        openid: openid,
        title: title,
        description: '1图变16款表情专属合集'
      },
      success: (res) => {
        wx.hideLoading();
        if (res.data && res.data.success && res.data.data && res.data.data.collection_id) {
          this.executeBatchSave(res.data.data.collection_id);
        } else {
          wx.showToast({ title: (res.data && res.data.detail) || '创建合集失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '创建合集失败', icon: 'none' });
      }
    });
  },

  // 批量存入选中的每张静态表情条目
  executeBatchSave(collectionId) {
    const selectedStickers = (this.data.stickersList || []).filter(s => s.selected);
    if (!selectedStickers.length) {
      wx.showToast({ title: '请至少勾选 1 款表情', icon: 'none' });
      return;
    }

    const openid = app.globalData.openid || wx.getStorageSync('openid') || '';
    const items = selectedStickers.map((s, idx) => ({
      gif_url: s.displayUrl || s.url,
      title: s.text || `表情 ${s.index !== undefined ? s.index + 1 : idx + 1}`
    }));

    this.setData({ isSavingBatch: true });
    wx.showLoading({ title: `正在存入 ${items.length} 张表情...`, mask: true });

    app.request({
      url: `${app.globalData.baseURL}/api/collection/add-items-batch`,
      method: 'POST',
      data: {
        collection_id: collectionId,
        openid: openid,
        items: items
      },
      success: (res) => {
        wx.hideLoading();
        this.setData({ isSavingBatch: false, showCollectionModal: false });
        if (res.data && res.data.success) {
          const count = (res.data.data && res.data.data.added_count) !== undefined ? res.data.data.added_count : items.length;
          wx.showToast({
            title: `成功存入 ${count} 张表情！`,
            icon: 'success',
            duration: 2200
          });
        } else {
          wx.showToast({ title: (res.data && res.data.detail) || '存入失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        this.setData({ isSavingBatch: false });
        wx.showToast({ title: '网络请求失败，请重试', icon: 'none' });
      }
    });
  }
});
