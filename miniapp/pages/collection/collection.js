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
    
    const formatCol = (item) => {
      let cover = item.cover_url || '';
      if (cover && cover.startsWith('/')) {
        cover = `${app.globalData.baseURL}${cover}`;
      }
      let preview_items = (item.preview_items || []).map(p => {
        let thumb = p.thumb_url || p.gif_url || '';
        if (thumb && thumb.startsWith('/')) {
          thumb = `${app.globalData.baseURL}${thumb}`;
        }
        return { ...p, thumb_url: thumb };
      });
      return { ...item, cover_url: cover, preview_items };
    };

    // 获取我的合集
    if (openid) {
      app.request({
        url: `${app.globalData.baseURL}/api/collection/my?openid=${openid}`,
        method: 'GET',
        success: (res) => {
          if (res.data && res.data.data) {
            const list = res.data.data.map(formatCol);
            this.setData({ myCollections: list });
          }
        }
      });
    }

    // 获取精选广场
    app.request({
      url: `${app.globalData.baseURL}/api/collection/explore`,
      method: 'GET',
      success: (res) => {
        if (res.data && res.data.data) {
          const list = res.data.data.map(formatCol);
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

    app.request({
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

    // 预先缓存合集摘要信息，让用户点击后详情页秒开无等待
    const all = [...(this.data.myCollections || []), ...(this.data.exploreCollections || [])];
    const found = all.find(c => c.collection_id === id);
    if (found) {
      wx.setStorageSync('cached_col_' + id, found);
    }

    wx.navigateTo({
      url: `/pages/collection/detail?id=${id}`
    });
  },

  goToMake() {
    wx.switchTab({ url: '/pages/index/index' });
  },

  saveItemToCol(colId, gifUrl) {
    wx.showLoading({ title: '正在加入合集...' });
    app.request({
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

  deleteCollection(e) {
    const id = e.currentTarget.dataset.id;
    const title = e.currentTarget.dataset.title || '该合集';
    const openid = app.globalData.openid || wx.getStorageSync('openid');

    if (id && (id.startsWith('col_tpl_') || id.startsWith('col_official_'))) {
      wx.showToast({ title: '精选广场官方合集不可删除', icon: 'none' });
      return;
    }

    wx.showModal({
      title: '确认删除合集',
      content: `确定要删除【${title}】吗？`,
      confirmColor: '#ef4444',
      success: (mRes) => {
        if (mRes.confirm) {
          wx.showLoading({ title: '正在删除...' });
          app.request({
            url: `${app.globalData.baseURL}/api/collection/delete`,
            method: 'POST',
            data: { collection_id: id, openid: openid },
            success: (res) => {
              wx.hideLoading();
              if (res.data && res.data.success) {
                wx.showToast({ title: '合集已删除', icon: 'success' });
                this.fetchData();
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

  stopBubble() {},

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
