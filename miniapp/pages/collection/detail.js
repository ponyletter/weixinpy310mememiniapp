const app = getApp();

Page({
  data: {
    collectionId: '',
    collection: {}
  },

  onLoad(options) {
    if (options && options.id) {
      this.setData({ collectionId: options.id });
      this.fetchDetail(options.id);
    }
  },

  onPullDownRefresh() {
    if (this.data.collectionId) {
      this.fetchDetail(this.data.collectionId, () => wx.stopPullDownRefresh());
    } else {
      wx.stopPullDownRefresh();
    }
  },

  fetchDetail(id, cb) {
    wx.showLoading({ title: '加载合集中...' });
    wx.request({
      url: `${app.globalData.baseURL}/api/collection/detail?collection_id=${id}`,
      method: 'GET',
      success: (res) => {
        wx.hideLoading();
        if (res.data && res.data.data) {
          const col = res.data.data;
          // 处理条目图片绝对路径
          if (col.items) {
            col.items = col.items.map(item => {
              let fullUrl = item.gif_url;
              if (fullUrl.startsWith('/')) {
                fullUrl = `${app.globalData.baseURL}${fullUrl}`;
              }
              return { ...item, full_url: fullUrl };
            });
          }
          this.setData({ collection: col });
          wx.setNavigationBarTitle({ title: col.title || '表情包合集' });
        }
        if (cb) cb();
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '加载失败', icon: 'none' });
      }
    });
  },

  formatUrl(url) {
    if (!url) return '';
    if (url.startsWith('http')) return url;
    return `${app.globalData.baseURL}${url}`;
  },

  previewOrSave(e) {
    const rawUrl = e.currentTarget.dataset.url;
    const url = rawUrl.startsWith('http') ? rawUrl : `${app.globalData.baseURL}${rawUrl}`;

    wx.showActionSheet({
      itemList: ['保存到手机相册', '预览大图'],
      success: (res) => {
        if (res.tapIndex === 0) {
          wx.showLoading({ title: '正在下载...' });
          wx.downloadFile({
            url: url,
            success: (dRes) => {
              wx.hideLoading();
              if (dRes.tempFilePath) {
                wx.saveImageToPhotosAlbum({
                  filePath: dRes.tempFilePath,
                  success: () => wx.showToast({ title: '已保存至相册！', icon: 'success' }),
                  fail: () => wx.showToast({ title: '保存失败，请检查权限', icon: 'none' })
                });
              }
            },
            fail: () => {
              wx.hideLoading();
              wx.showToast({ title: '下载失败', icon: 'none' });
            }
          });
        } else if (res.tapIndex === 1) {
          wx.previewImage({
            urls: [url],
            current: url
          });
        }
      }
    });
  },

  goToMake() {
    wx.switchTab({ url: '/pages/index/index' });
  },

  onShareAppMessage() {
    const col = this.data.collection;
    return {
      title: `送你一组精选【${col.title || '表情包'}】合集，快来看看！`,
      path: `/pages/collection/detail?id=${this.data.collectionId}`,
      imageUrl: col.cover_url || ''
    };
  }
});
