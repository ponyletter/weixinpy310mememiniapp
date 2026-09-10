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

  deleteItem(e) {
    const itemId = e.currentTarget.dataset.id;
    if (!itemId) return;

    wx.showModal({
      title: '确认移除',
      content: '确定要从该合集中移除这张表情吗？',
      confirmColor: '#ef4444',
      success: (mRes) => {
        if (mRes.confirm) {
          wx.showLoading({ title: '正在移除...' });
          wx.request({
            url: `${app.globalData.baseURL}/api/collection/item/delete`,
            method: 'POST',
            data: { item_id: itemId },
            success: (res) => {
              wx.hideLoading();
              if (res.data && res.data.success) {
                wx.showToast({ title: '已移除', icon: 'success' });
                this.fetchDetail(this.data.collectionId);
              } else {
                wx.showToast({ title: '移除失败', icon: 'none' });
              }
            },
            fail: () => {
              wx.hideLoading();
              wx.showToast({ title: '网络超时', icon: 'none' });
            }
          });
        }
      }
    });
  },

  deleteCurrentCollection() {
    const col = this.data.collection;
    const id = this.data.collectionId;
    if (!id) return;
    const openid = app.globalData.openid || wx.getStorageSync('openid');

    wx.showModal({
      title: '确认删除合集',
      content: `确定要删除合集【${col.title || '此合集'}】吗？删除后合集内的所有表情归档将被移除。`,
      confirmColor: '#ef4444',
      success: (mRes) => {
        if (mRes.confirm) {
          wx.showLoading({ title: '正在删除...' });
          wx.request({
            url: `${app.globalData.baseURL}/api/collection/delete`,
            method: 'POST',
            data: { collection_id: id, openid: openid },
            success: (res) => {
              wx.hideLoading();
              if (res.data && res.data.success) {
                wx.showToast({ title: '合集已成功删除', icon: 'success' });
                setTimeout(() => {
                  wx.switchTab({ url: '/pages/collection/collection' });
                }, 800);
              } else {
                wx.showToast({ title: (res.data && res.data.detail) || '删除失败', icon: 'none' });
              }
            },
            fail: () => {
              wx.hideLoading();
              wx.showToast({ title: '网络超时', icon: 'none' });
            }
          });
        }
      }
    });
  },

  saveMemeDirect(e) {
    const rawUrl = e.currentTarget.dataset.url;
    if (!rawUrl) return;
    const url = rawUrl.startsWith('http') ? rawUrl : `${app.globalData.baseURL}${rawUrl}`;

    wx.showLoading({ title: '正在保存到相册...' });
    wx.downloadFile({
      url: url,
      success: (dRes) => {
        wx.hideLoading();
        if (dRes.tempFilePath) {
          wx.saveImageToPhotosAlbum({
            filePath: dRes.tempFilePath,
            success: () => wx.showToast({ title: '已保存至手机相册！', icon: 'success' }),
            fail: (err) => {
              console.error(err);
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

  onShareAppMessage() {
    const col = this.data.collection;
    return {
      title: `送你一组精选【${col.title || '表情包'}】合集，快来看看！`,
      path: `/pages/collection/detail?id=${this.data.collectionId}`,
      imageUrl: col.cover_url || ''
    };
  }
});
