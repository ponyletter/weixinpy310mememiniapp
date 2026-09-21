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
      { id: 'worker', name: '打工人日常', desc: '好的收到/搬砖/谢老板', icon: '💼' },
      { id: 'battle', name: '群聊斗图', desc: '问号脸/退退退/就这', icon: '⚡' },
      { id: 'cute', name: '萌系可爱', desc: '比心/抱抱/委屈/卖萌', icon: '💖' },
      { id: 'slack', name: '摆烂躺平', desc: '开摆/随缘/无所谓啦', icon: '🍵' },
      { id: 'daily', name: '日常高频', desc: 'OK/点赞/摸鱼/干饭', icon: '💬' }
    ],

    stylePresets: [
      { id: 'wechat_sticker', icon: '✨', name: '经典手绘', desc: '2D扁平·原生贴纸感' },
      { id: 'real_person', icon: '📸', name: '写实真人', desc: '真实摄影·生动还原' },
      { id: 'cute_chibi', icon: '🐱', name: 'Q版萌系', desc: '圆润大眼·治愈可爱' },
      { id: 'funny_line', icon: '✏️', name: '沙雕线描', desc: '黑白线稿·斗图神作' },
      { id: '3d_toy', icon: '🧸', name: '3D公仔', desc: '立体潮玩·盲盒质感' },
      { id: 'custom', icon: '🎨', name: '自定义画风', desc: '输入专属画风词' }
    ],

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

  // 存入合集 (TabBar 页面需使用 switchTab)
  saveToMyCollection() {
    const firstSticker = this.data.stickersList[0];
    if (!firstSticker) return;
    wx.setStorageSync('pending_add_gif', firstSticker.displayUrl);
    wx.showToast({ title: '正在转入合集...', icon: 'loading', duration: 600 });
    setTimeout(() => {
      wx.switchTab({
        url: '/pages/collection/collection'
      });
    }, 300);
  }
});
