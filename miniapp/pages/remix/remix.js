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
      wx.showToast({ title: '请上传动图', icon: 'none' });
      return;
    }
    if (!this.data.captionText.trim()) {
      wx.showToast({ title: '请输入新台词', icon: 'none' });
      return;
    }

    this.setData({ isConverting: true });
    wx.showLoading({ title: '正在改字重绘...' });

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
          wx.showToast({ title: '改字成功！', icon: 'success' });
        } else {
          wx.showToast({ title: '改字失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        this.setData({ isConverting: false });
      }
    });
  },

  saveRemixGif() {
    if (!this.data.remixResultUrl) return;
    wx.downloadFile({
      url: this.data.remixResultUrl,
      success: (res) => {
        if (res.tempFilePath) {
          wx.saveImageToPhotosAlbum({
            filePath: res.tempFilePath,
            success: () => wx.showToast({ title: '已保存至相册', icon: 'success' }),
            fail: () => wx.showToast({ title: '保存失败', icon: 'none' })
          });
        }
      }
    });
  },

  addToCollection() {
    if (!this.data.remixResultUrl) return;
    wx.navigateTo({
      url: `/pages/collection/collection?add_gif=${encodeURIComponent(this.data.remixResultUrl)}`
    });
  }
});
