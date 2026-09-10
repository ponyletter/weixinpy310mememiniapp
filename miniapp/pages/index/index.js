const app = getApp();

Page({
  data: {
    quota: 10,
    isVip: false,
    templates: [],
    selectedTemplate: 'kiss',
    selectedTemplateTitle: '飞吻',
    mode: 'upload', // 'upload' | 'sketch'
    refImagePath: '',
    characterDesc: '',
    caption: '么么哒',
    isGenerating: false,
    progress: 0,
    stageText: '',
    gifResultUrl: '',
    taskId: '',
    showFullScreenSketch: false,
    fsColor: '#1e293b',
    fsLineWidth: 6,
    sketchTempPath: '',
    showCollectionModal: false,
    userCollections: [],
    selectedColId: '',
    newColTitle: ''
  },

  onLoad() {
    this.fetchTemplates();
    this.updateQuotaInfo();
    this.initSketchCanvas();
    this.checkResumeActiveTask();
  },

  onShow() {
    this.updateQuotaInfo();
    this.checkResumeActiveTask();
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
    wx.request({
      url: `${app.globalData.baseURL}/api/templates`,
      method: 'GET',
      success: (res) => {
        if (res.data && res.data.data) {
          const list = res.data.data;
          this.setData({
            templates: list,
            selectedTemplateTitle: (list.find(t => t.id === this.data.selectedTemplate) || {}).title || '飞吻'
          });
        }
      }
    });
  },

  selectTemplate(e) {
    const { id, title, caption } = e.currentTarget.dataset;
    this.setData({
      selectedTemplate: id,
      selectedTemplateTitle: title || id,
      caption: caption || this.data.caption
    });
  },

  switchMode(e) {
    const mode = e.currentTarget.dataset.mode;
    this.setData({ mode });
    if (mode === 'sketch') {
      setTimeout(() => this.initSketchCanvas(), 200);
    }
  },

  // --- 图片上传 ---
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

  removeImage() {
    this.setData({ refImagePath: '' });
  },

  onInputDesc(e) {
    this.setData({ characterDesc: e.detail.value });
  },

  onInputCaption(e) {
    this.setData({ caption: e.detail.value });
  },

  getCaptionSuggestions() {
    wx.showLoading({ title: '正在提取灵感...' });
    wx.request({
      url: `${app.globalData.baseURL}/api/convert/caption-suggest`,
      method: 'POST',
      header: { 'content-type': 'application/x-www-form-urlencoded' },
      data: { keyword: this.data.characterDesc || '摸鱼' },
      success: (res) => {
        wx.hideLoading();
        if (res.data && res.data.suggestions) {
          const items = res.data.suggestions.map(s => `[${s.style}] ${s.text}`);
          wx.showActionSheet({
            itemList: items,
            success: (aRes) => {
              const picked = res.data.suggestions[aRes.tapIndex].text;
              this.setData({ caption: picked });
            }
          });
        }
      },
      fail: () => {
        wx.hideLoading();
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
        const dpr = wx.getSystemInfoSync().pixelRatio;
        canvas.width = res[0].width * dpr;
        canvas.height = res[0].height * dpr;
        ctx.scale(dpr, dpr);
        ctx.strokeStyle = '#1e293b';
        ctx.lineWidth = 4;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        this.sketchCanvas = canvas;
        this.sketchCtx = ctx;
      });
  },

  onSketchStart(e) {
    if (!this.sketchCtx) return;
    const touch = e.touches[0];
    this.sketchCtx.beginPath();
    this.sketchCtx.moveTo(touch.x, touch.y);
  },

  onSketchMove(e) {
    if (!this.sketchCtx) return;
    const touch = e.touches[0];
    this.sketchCtx.lineTo(touch.x, touch.y);
    this.sketchCtx.stroke();
  },

  onSketchEnd() {
    if (!this.sketchCtx) return;
    this.sketchCtx.closePath();
  },

  clearSketch() {
    if (!this.sketchCanvas || !this.sketchCtx) return;
    this.sketchCtx.clearRect(0, 0, this.sketchCanvas.width, this.sketchCanvas.height);
    this.setData({ sketchTempPath: '' });
  },

  // --- 全屏涂鸦画板 ---
  openFullScreenSketch() {
    this.setData({ showFullScreenSketch: true });
    setTimeout(() => {
      this.initFullScreenCanvas();
    }, 200);
  },

  closeFullScreenSketch() {
    this.setData({ showFullScreenSketch: false });
  },

  initFullScreenCanvas() {
    const query = wx.createSelectorQuery();
    query.select('#fullScreenCanvas')
      .fields({ node: true, size: true })
      .exec((res) => {
        if (!res[0] || !res[0].node) return;
        const canvas = res[0].node;
        const ctx = canvas.getContext('2d');
        const dpr = wx.getSystemInfoSync().pixelRatio;
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
            ctx.drawImage(img, 0, 0, res[0].width, res[0].height);
          };
          img.src = this.data.sketchTempPath;
        }
      });
  },

  onFSSketchStart(e) {
    if (!this.fsCtx) return;
    const touch = e.touches[0];
    this.fsCtx.beginPath();
    this.fsCtx.strokeStyle = this.data.fsColor;
    this.fsCtx.lineWidth = this.data.fsLineWidth;
    this.fsCtx.moveTo(touch.x, touch.y);
  },

  onFSSketchMove(e) {
    if (!this.fsCtx) return;
    const touch = e.touches[0];
    this.fsCtx.lineTo(touch.x, touch.y);
    this.fsCtx.stroke();
  },

  onFSSketchEnd() {
    if (!this.fsCtx) return;
    this.fsCtx.closePath();
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
    this.fsCtx.clearRect(0, 0, this.fsCanvas.width, this.fsCanvas.height);
    this.setData({ sketchTempPath: '' });
  },

  saveAndSyncFullScreenSketch() {
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

    this.setData({
      isGenerating: true,
      progress: 5,
      stageText: '正在启动极速渲染引擎...',
      gifResultUrl: ''
    });

    const gifConfig = app.getGifConfig();
    const formData = {
      action_type: this.data.selectedTemplate,
      character_desc: this.data.characterDesc,
      custom_caption: this.data.caption,
      fps: gifConfig.fps || 8,
      resolution: gifConfig.resolution || '240x240',
      fast_mode: gifConfig.fastMode ? '1' : '0',
      loop_count: gifConfig.loopCount || 0,
      openid: app.globalData.openid || '',
      is_sketch: this.data.mode === 'sketch' ? '1' : '0'
    };

    const uploadUrl = `${app.globalData.baseURL}/api/generate-async`;

    if (this.data.mode === 'upload' && this.data.refImagePath) {
      wx.uploadFile({
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
        wx.uploadFile({
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
            wx.uploadFile({
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
    wx.request({
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
      this.setData({ taskId });
      wx.setStorageSync('active_meme_task', {
        taskId: taskId,
        timestamp: Date.now()
      });
      this.pollTaskStatus(taskId);
      this.updateQuotaInfo();
    } else {
      this.handleGenerateError((data && data.detail) || "启动任务失败");
    }
  },

  pollTaskStatus(taskId) {
    if (this.pollTimer) clearInterval(this.pollTimer);
    this.pollTimer = setInterval(() => {
      wx.request({
        url: `${app.globalData.baseURL}/api/task-status/${taskId}`,
        method: 'GET',
        success: (res) => {
          if (res.data && res.data.data) {
            const tInfo = res.data.data;
            this.setData({
              progress: tInfo.progress || 10,
              stageText: tInfo.stage_text || '逐帧渲染处理中...'
            });

            if (tInfo.status === 'completed') {
              clearInterval(this.pollTimer);
              wx.removeStorageSync('active_meme_task');
              const gifPath = tInfo.data.gif_url;
              this.setData({
                isGenerating: false,
                gifResultUrl: `${app.globalData.baseURL}${gifPath}`,
                progress: 100
              });
              wx.showToast({ title: '制作成功！', icon: 'success' });
            } else if (tInfo.status === 'failed') {
              clearInterval(this.pollTimer);
              wx.removeStorageSync('active_meme_task');
              this.handleGenerateError(tInfo.error || "生成异常");
            }
          }
        },
        fail: () => {
          // 网络抖动不打断轮询
        }
      });
    }, 1500);
  },

  handleGenerateError(msg) {
    if (this.pollTimer) clearInterval(this.pollTimer);
    wx.removeStorageSync('active_meme_task');
    this.setData({ isGenerating: false });
    wx.showModal({
      title: '制作提示',
      content: msg || '制作任务响应超时，已为您自动返还制作额度！',
      showCancel: false
    });
    this.updateQuotaInfo();
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

  // --- 存入表情合集 (支持自动建合集与抽屉管理) ---
  openAddToCollection() {
    if (!this.data.gifResultUrl) return;
    const openid = app.globalData.openid || wx.getStorageSync('openid');
    if (!openid) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }

    wx.showLoading({ title: '获取合集中...' });
    wx.request({
      url: `${app.globalData.baseURL}/api/collection/my?openid=${openid}`,
      method: 'GET',
      success: (res) => {
        wx.hideLoading();
        let cols = (res.data && res.data.data) || [];
        if (cols.length === 0) {
          // 首次使用自动为用户创建“我的精选表情集”
          wx.request({
            url: `${app.globalData.baseURL}/api/collection/create`,
            method: 'POST',
            data: {
              openid: openid,
              title: '我的精选表情集',
              description: '默认表情包收纳抽屉'
            },
            success: (cRes) => {
              if (cRes.data && cRes.data.data) {
                const defaultCol = cRes.data.data;
                this.setData({
                  userCollections: [defaultCol],
                  selectedColId: defaultCol.collection_id,
                  showCollectionModal: true
                });
              }
            }
          });
        } else {
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
    wx.request({
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
    wx.request({
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
    wx.request({
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
    app.invokeVirtualPayment('item_100', () => {
      this.updateQuotaInfo();
    });
  }
});

