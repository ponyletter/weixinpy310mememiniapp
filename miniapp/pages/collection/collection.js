const app = getApp();

Page({
  data: {
    activeTab: 'my', // 'my' | 'explore'
    myCollections: [],
    exploreCollections: [],
    showCreateModal: false,
    newTitle: '',
    newDesc: '',
    pendingGifUrl: '',
    currentShareItem: null
  },

  onLoad(options) {
    if (options && options.add_gif) {
      this.setData({
        pendingGifUrl: decodeURIComponent(options.add_gif)
      });
      wx.showToast({ title: '请选择存入的合集', icon: 'none' });
    }
    this.fetchData();
  },

  onShow() {
    this.fetchData();
  },

  onPullDownRefresh() {
    this.fetchData(() => wx.stopPullDownRefresh());
  },

  switchTab(e) {
    this.setData({ activeTab: e.currentTarget.dataset.tab });
  },

  fetchData(cb) {
    const openid = app.globalData.openid || wx.getStorageSync('openid');
    
    // 获取我的合集
    if (openid) {
      wx.request({
        url: `${app.globalData.baseURL}/api/collection/my?openid=${openid}`,
        method: 'GET',
        success: (res) => {
          if (res.data && res.data.data) {
            const list = res.data.data.map(item => {
              let cover = item.cover_url || '';
              if (cover && cover.startsWith('/')) {
                cover = `${app.globalData.baseURL}${cover}`;
              }
              return { ...item, cover_url: cover };
            });
            this.setData({ myCollections: list });
          }
        }
      });
    }

    // 获取精选广场
    wx.request({
      url: `${app.globalData.baseURL}/api/collection/explore`,
      method: 'GET',
      success: (res) => {
        if (res.data && res.data.data) {
          const list = res.data.data.map(item => {
            let cover = item.cover_url || '';
            if (cover && cover.startsWith('/')) {
              cover = `${app.globalData.baseURL}${cover}`;
            }
            return { ...item, cover_url: cover };
          });
          this.setData({ exploreCollections: list });
        }
        if (cb) cb();
      }
    });
  },

  openCreateModal() {
    this.setData({
      showCreateModal: true,
      newTitle: '',
      newDesc: ''
    });
  },

  closeCreateModal() {
    this.setData({ showCreateModal: false });
  },

  onInputTitle(e) {
    this.setData({ newTitle: e.detail.value });
  },

  onInputDesc(e) {
    this.setData({ newDesc: e.detail.value });
  },

  submitCreateCollection() {
    if (!this.data.newTitle.trim()) {
      wx.showToast({ title: '请输入合集名称', icon: 'none' });
      return;
    }

    const openid = app.globalData.openid || wx.getStorageSync('openid');
    wx.showLoading({ title: '创建中...' });

    wx.request({
      url: `${app.globalData.baseURL}/api/collection/create`,
      method: 'POST',
      data: {
        openid: openid,
        title: this.data.newTitle.trim(),
        description: this.data.newDesc.trim()
      },
      success: (res) => {
        wx.hideLoading();
        if (res.data && res.data.success) {
          wx.showToast({ title: '合集创建成功！', icon: 'success' });
          this.closeCreateModal();
          this.fetchData();

          // 如果有挂起的表情包，顺手存入
          if (this.data.pendingGifUrl) {
            this.saveItemToCol(res.data.data.collection_id, this.data.pendingGifUrl);
          }
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '创建失败', icon: 'none' });
      }
    });
  },

  goToDetail(e) {
    const id = e.currentTarget.dataset.id;
    if (this.data.pendingGifUrl) {
      // 存入合集动作
      this.saveItemToCol(id, this.data.pendingGifUrl);
      return;
    }

    wx.navigateTo({
      url: `/pages/collection/detail?id=${id}`
    });
  },

  saveItemToCol(colId, gifUrl) {
    wx.showLoading({ title: '正在加入合集...' });
    wx.request({
      url: `${app.globalData.baseURL}/api/collection/add-item`,
      method: 'POST',
      data: {
        collection_id: colId,
        gif_url: gifUrl,
        title: '我的表情包'
      },
      success: (res) => {
        wx.hideLoading();
        if (res.data && res.data.success) {
          wx.showToast({ title: '已成功存入合集！', icon: 'success' });
          this.setData({ pendingGifUrl: '' });
          this.fetchData();
        }
      }
    });
  },

  setShareTarget(e) {
    this.setData({ currentShareItem: e.currentTarget.dataset.item });
  },

  onShareAppMessage() {
    const item = this.data.currentShareItem;
    if (item) {
      return {
        title: `送你一组精选【${item.title}】表情包，快来存！`,
        path: `/pages/collection/detail?id=${item.collection_id}`,
        imageUrl: item.cover_url || ''
      };
    }
    return {
      title: 'GIF表情包制作神器 - 看到素材一键做动图！',
      path: '/pages/index/index'
    };
  }
});
