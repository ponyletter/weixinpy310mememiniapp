const app = getApp();

Page({
  data: {
    tab: 'video', // 'video' | 'images' | 'caption'
    videoPath: '',
    multiImages: [],
    srcGifPath: '',
    captionText: '',
    isConverting: false,
    remixResultUrl: ''
  },

  onLoad(options) {
    if (options && options.material) {
      // 聊天素材传入
      this.handleIncomingMaterial(options.material);
    }
  },

  switchTab(e) {
    const tab = e.currentTarget.dataset.tab;
    this.setData({
      tab,
      remixResultUrl: '',
      captionText: ''
    });
  },

  onInputCaption(e) {
    this.setData({ captionText: e.detail.value });
  },

  // 1. 视频转动图
  chooseVideo() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['video'],
      maxDuration: 30,
      success: (res) => {
        if (res.tempFiles && res.tempFiles.length > 0) {
          this.setData({ videoPath: res.tempFiles[0].tempFilePath });
        }
      }
    });
  },

  clearVideo() {
    this.setData({ videoPath: '' });
  },

  convertVideoToGif() {
    if (!this.data.videoPath) {
      wx.showToast({ title: '请先选择视频', icon: 'none' });
      return;
    }

    this.setData({ isConverting: true });
    wx.showLoading({ title: '正在提取精彩动图...' });

    wx.uploadFile({
      url: `${app.globalData.baseURL}/api/convert/video-to-gif`,
      filePath: this.data.videoPath,
      name: 'video',
      formData: {
        caption: this.data.captionText,
        duration: 3.0,
        fps: 10,
        width: 240
      },
      success: (res) => {
        wx.hideLoading();
        this.setData({ isConverting: false });
        let data = res.data;
        if (typeof data === 'string') {
          try { data = JSON.parse(data); } catch(e) {}
        }
        if (data && data.success) {
          this.setData({ remixResultUrl: `${app.globalData.baseURL}${data.gif_url}` });
          wx.showToast({ title: '转动图成功！', icon: 'success' });
        } else {
          wx.showToast({ title: (data && data.detail) || '转换失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        this.setData({ isConverting: false });
        wx.showToast({ title: '网络请求超时', icon: 'none' });
      }
    });
  },

  // 2. 多图合成动图
  chooseMultiImages() {
    wx.chooseMedia({
      count: 9 - this.data.multiImages.length,
      mediaType: ['image'],
      success: (res) => {
        if (res.tempFiles && res.tempFiles.length > 0) {
          const newPaths = res.tempFiles.map(f => f.tempFilePath);
          this.setData({
            multiImages: [...this.data.multiImages, ...newPaths]
          });
        }
      }
    });
  },

  convertImagesToGif() {
    if (this.data.multiImages.length < 2) {
      wx.showToast({ title: '至少需要2张图片', icon: 'none' });
      return;
    }

    this.setData({ isConverting: true });
    wx.showLoading({ title: '正在拼接连续动图...' });

    // 多文件上传
    wx.uploadFile({
      url: `${app.globalData.baseURL}/api/convert/images-to-gif`,
      filePath: this.data.multiImages[0],
      name: 'files',
      formData: {
        caption: this.data.captionText,
        fps: 4
      },
      success: (res) => {
        wx.hideLoading();
        this.setData({ isConverting: false });
        let data = res.data;
        try { data = JSON.parse(data); } catch(e) {}
        if (data && data.success) {
          this.setData({ remixResultUrl: `${app.globalData.baseURL}${data.gif_url}` });
          wx.showToast({ title: '合成成功！', icon: 'success' });
        } else {
          wx.showToast({ title: '拼接失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        this.setData({ isConverting: false });
      }
    });
  },

  // 3. 表情包改字
  chooseGifToEdit() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      success: (res) => {
        if (res.tempFiles && res.tempFiles.length > 0) {
          this.setData({ srcGifPath: res.tempFiles[0].tempFilePath });
        }
      }
    });
  },

  clearSrcGif() {
    this.setData({ srcGifPath: '' });
  },

  editGifCaption() {
    if (!this.data.srcGifPath) {
      wx.showToast({ title: '请上传图片或动图', icon: 'none' });
      return;
    }
    if (!this.data.captionText.trim()) {
      wx.showToast({ title: '请输入台词字幕', icon: 'none' });
      return;
    }

    this.setData({ isConverting: true });
    wx.showLoading({ title: '正在合成表情包...' });

    wx.uploadFile({
      url: `${app.globalData.baseURL}/api/convert/edit-caption`,
      filePath: this.data.srcGifPath,
      name: 'gif_file',
      formData: {
        caption: this.data.captionText.trim()
      },
      success: (res) => {
        wx.hideLoading();
        this.setData({ isConverting: false });
        let data = res.data;
        try { data = JSON.parse(data); } catch(e) {}
        if (data && data.success) {
          this.setData({ remixResultUrl: `${app.globalData.baseURL}${data.gif_url}` });
          wx.showToast({ title: '合成成功！', icon: 'success' });
        } else {
          wx.showToast({ title: (data && data.detail) || '合成失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        this.setData({ isConverting: false });
        wx.showToast({ title: '网络超时', icon: 'none' });
      }
    });
  },

  saveRemixGif() {
    if (!this.data.remixResultUrl) return;
    wx.showLoading({ title: '正在下载...' });
    wx.downloadFile({
      url: this.data.remixResultUrl,
      success: (res) => {
        wx.hideLoading();
        if (res.tempFilePath) {
          wx.saveImageToPhotosAlbum({
            filePath: res.tempFilePath,
            success: () => wx.showToast({ title: '已保存至相册', icon: 'success' }),
            fail: () => wx.showToast({ title: '保存失败', icon: 'none' })
          });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '下载失败', icon: 'none' });
      }
    });
  },

  addToCollection() {
    if (!this.data.remixResultUrl) return;
    const openid = app.globalData.openid || wx.getStorageSync('openid');
    wx.showLoading({ title: '正在存入...' });
    wx.request({
      url: `${app.globalData.baseURL}/api/collection/list?openid=${openid}`,
      method: 'GET',
      success: (res) => {
        let cols = (res.data && res.data.data) || [];
        const saveToCol = (colId) => {
          wx.request({
            url: `${app.globalData.baseURL}/api/collection/add-item`,
            method: 'POST',
            data: {
              collection_id: colId,
              gif_url: this.data.remixResultUrl,
              title: this.data.captionText || '二创表情'
            },
            success: (sRes) => {
              wx.hideLoading();
              wx.showModal({
                title: '存入成功 🎉',
                content: '已成功存入表情合集！可前往底栏【表情合集】查看或打包分享给好友。',
                confirmText: '前往查看',
                cancelText: '留在本页',
                success: (mRes) => {
                  if (mRes.confirm) {
                    wx.switchTab({ url: '/pages/collection/collection' });
                  }
                }
              });
            },
            fail: () => {
              wx.hideLoading();
              wx.showToast({ title: '存入失败', icon: 'none' });
            }
          });
        };

        if (cols.length === 0) {
          wx.request({
            url: `${app.globalData.baseURL}/api/collection/create`,
            method: 'POST',
            data: { openid: openid, title: '我的精选表情', description: '默认表情合集' },
            success: (cRes) => {
              if (cRes.data && cRes.data.data) {
                saveToCol(cRes.data.data.collection_id);
              } else {
                wx.hideLoading();
                wx.showToast({ title: '初始化合集失败', icon: 'none' });
              }
            },
            fail: () => {
              wx.hideLoading();
              wx.showToast({ title: '网络连接异常', icon: 'none' });
            }
          });
        } else {
          saveToCol(cols[0].collection_id);
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '网络异常', icon: 'none' });
      }
    });
  },

  onShareAppMessage(options) {
    const user = (app.globalData && app.globalData.userInfo) || {};
    const inviteCode = user.invite_code || app.globalData.inviterCode || '';

    if (this.data.remixResultUrl) {
      const cap = this.data.captionText || '神配文';
      return {
        title: `🔥 看看我给表情包配的文案【${cap}】，太真实了！`,
        path: `/pages/remix/remix?inviter=${inviteCode}`,
        imageUrl: this.data.remixResultUrl
      };
    }

    return {
      title: '表情包自由！一键神配文二次创作你的专属动图',
      path: `/pages/remix/remix?inviter=${inviteCode}`
    };
  },

  onShareTimeline() {
    const cap = this.data.captionText || '神配文';
    return {
      title: `我二创了【${cap}】表情包，快来试试！`,
      imageUrl: this.data.remixResultUrl || ''
    };
  }
});
