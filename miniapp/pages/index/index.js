const app = getApp();

Page({
  data: {
    quota: 10,
    isVip: false,
    templates: [],
    selectedTemplate: 'kiss',
    mode: 'upload', // 'upload' | 'sketch'
    refImagePath: '',
    characterDesc: '可爱的白色柴犬',
    caption: '么么哒',
    isGenerating: false,
    progress: 0,
    stageText: '',
    gifResultUrl: '',
    taskId: '',
    
    // 贪吃蛇小游戏
    snakeScore: 0,
    showSnake: true
  },

  onLoad() {
    this.fetchTemplates();
    this.updateQuotaInfo();
    this.initSketchCanvas();
  },

  onShow() {
    this.updateQuotaInfo();
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
          this.setData({ templates: res.data.data });
        }
      }
    });
  },

  selectTemplate(e) {
    const { id, caption } = e.currentTarget.dataset;
    this.setData({
      selectedTemplate: id,
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

  getAiSuggestions() {
    wx.showLoading({ title: 'AI灵感激发中...' });
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

  // --- 草图画板实现 ---
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
        ctx.strokeStyle = '#ffffff';
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
  },

  // --- 提交生成 ---
  startGenerate() {
    if (this.data.isGenerating) return;

    if (this.data.quota <= 0 && !this.data.isVip) {
      wx.showModal({
        title: '制作额度不足',
        content: '新用户已赠送10次已用完。仅需 1.00 元即可开通 20 次超值尝鲜包，是否立即充值？',
        confirmText: '1元充值',
        cancelText: '去签到',
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
      stageText: '正在启动任务...',
      gifResultUrl: ''
    });

    // 启动贪吃蛇游戏
    setTimeout(() => {
      this.initSnakeGame();
    }, 200);

    const formData = {
      action_type: this.data.selectedTemplate,
      character_desc: this.data.characterDesc,
      custom_caption: this.data.caption,
      fps: 8,
      openid: app.globalData.openid || '',
      is_sketch: this.data.mode === 'sketch'
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
          this.handleGenerateError("网络传输失败");
        }
      });
    } else if (this.data.mode === 'sketch' && this.sketchCanvas) {
      // 导出画布图片
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
              this.handleGenerateError("草图上传失败");
            }
          });
        },
        fail: () => {
          // 直接表单上传
          this.postFormGenerate(uploadUrl, formData);
        }
      });
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
        this.handleGenerateError("请求失败");
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
      this.pollTaskStatus(taskId);
      this.updateQuotaInfo();
    } else {
      this.handleGenerateError((data && data.detail) || "启动任务失败");
    }
  },

  pollTaskStatus(taskId) {
    this.pollTimer = setInterval(() => {
      wx.request({
        url: `${app.globalData.baseURL}/api/task-status/${taskId}`,
        method: 'GET',
        success: (res) => {
          if (res.data && res.data.data) {
            const tInfo = res.data.data;
            this.setData({
              progress: tInfo.progress || 10,
              stageText: tInfo.stage_text || 'AI绘制中...'
            });

            if (tInfo.status === 'completed') {
              clearInterval(this.pollTimer);
              const gifPath = tInfo.data.gif_url;
              this.setData({
                isGenerating: false,
                gifResultUrl: `${app.globalData.baseURL}${gifPath}`,
                progress: 100
              });
              wx.showToast({ title: '动图生成成功！', icon: 'success' });
            } else if (tInfo.status === 'failed') {
              clearInterval(this.pollTimer);
              this.handleGenerateError(tInfo.error || "出图失败");
            }
          }
        }
      });
    }, 1500);
  },

  handleGenerateError(msg) {
    clearInterval(this.pollTimer);
    this.setData({ isGenerating: false });
    wx.showModal({
      title: '生成异常',
      content: msg || 'AI生成超时或异常，已为您自动返还额度！',
      showCancel: false
    });
    this.updateQuotaInfo();
  },

  // --- 贪吃蛇小游戏实现 ---
  initSnakeGame() {
    const query = wx.createSelectorQuery();
    query.select('#snakeCanvas')
      .fields({ node: true, size: true })
      .exec((res) => {
        if (!res[0] || !res[0].node) return;
        const canvas = res[0].node;
        const ctx = canvas.getContext('2d');
        this.snakeCanvas = canvas;
        this.snakeCtx = ctx;

        this.gridSize = 14;
        this.cols = Math.floor(res[0].width / this.gridSize);
        this.rows = Math.floor(res[0].height / this.gridSize);

        this.restartSnake();
      });
  },

  restartSnake() {
    this.snake = [
      { x: 5, y: 5 },
      { x: 4, y: 5 },
      { x: 3, y: 5 }
    ];
    this.snakeDir = 'RIGHT';
    this.nextDir = 'RIGHT';
    this.spawnFood();
    this.setData({ snakeScore: 0 });

    if (this.snakeLoop) clearInterval(this.snakeLoop);
    this.snakeLoop = setInterval(() => {
      this.updateSnake();
    }, 120);
  },

  spawnFood() {
    this.food = {
      x: Math.floor(Math.random() * (this.cols - 2)) + 1,
      y: Math.floor(Math.random() * (this.rows - 2)) + 1
    };
  },

  updateSnake() {
    if (!this.snakeCtx) return;
    this.snakeDir = this.nextDir;
    const head = { ...this.snake[0] };

    if (this.snakeDir === 'UP') head.y--;
    else if (this.snakeDir === 'DOWN') head.y++;
    else if (this.snakeDir === 'LEFT') head.x--;
    else if (this.snakeDir === 'RIGHT') head.x++;

    // 撞墙穿墙
    if (head.x < 0) head.x = this.cols - 1;
    if (head.x >= this.cols) head.x = 0;
    if (head.y < 0) head.y = this.rows - 1;
    if (head.y >= this.rows) head.y = 0;

    // 撞自身重开
    for (let i = 1; i < this.snake.length; i++) {
      if (this.snake[i].x === head.x && this.snake[i].y === head.y) {
        this.restartSnake();
        return;
      }
    }

    this.snake.unshift(head);

    // 吃食物
    if (head.x === this.food.x && head.y === this.food.y) {
      this.setData({ snakeScore: this.data.snakeScore + 1 });
      this.spawnFood();
    } else {
      this.snake.pop();
    }

    this.drawSnake();
  },

  drawSnake() {
    const ctx = this.snakeCtx;
    ctx.clearRect(0, 0, this.snakeCanvas.width, this.snakeCanvas.height);

    // 画食物
    ctx.fillStyle = '#f59e0b';
    ctx.fillRect(this.food.x * this.gridSize, this.food.y * this.gridSize, this.gridSize - 2, this.gridSize - 2);

    // 画蛇
    ctx.fillStyle = '#10b981';
    for (let i = 0; i < this.snake.length; i++) {
      if (i === 0) ctx.fillStyle = '#34d399';
      else ctx.fillStyle = '#059669';
      ctx.fillRect(this.snake[i].x * this.gridSize, this.snake[i].y * this.gridSize, this.gridSize - 2, this.gridSize - 2);
    }
  },

  changeSnakeDir(e) {
    const dir = e.currentTarget.dataset.dir;
    const opp = { UP: 'DOWN', DOWN: 'UP', LEFT: 'RIGHT', RIGHT: 'LEFT' };
    if (opp[dir] !== this.snakeDir) {
      this.nextDir = dir;
    }
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
              wx.showToast({ title: '已保存至相册！', icon: 'success' });
            },
            fail: () => {
              wx.showToast({ title: '保存失败，请检查相册权限', icon: 'none' });
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

  openAddToCollection() {
    wx.showModal({
      title: '存入合集',
      content: '是否将此表情包归类到我的表情抽屉中？',
      confirmText: '立即归类',
      success: (res) => {
        if (res.confirm) {
          wx.navigateTo({
            url: `/pages/collection/collection?add_gif=${encodeURIComponent(this.data.gifResultUrl)}`
          });
        }
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
  },

  preventBubble() {}
});
