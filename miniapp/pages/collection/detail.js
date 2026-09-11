const app = getApp();

Page({
  data: {
    collectionId: '',
    collection: {},
    isOwner: false,
    detailLoading: false,
    detailError: false
  },

  onLoad(options) {
    if (options && options.id) {
      const colId = options.id;
      this.setData({ collectionId: colId, detailLoading: true, detailError: false });

      // 优先从缓存加载头部信息与预览表情条目，实现 0 毫秒秒开，彻底告别白屏和长时间等待
      const cached = wx.getStorageSync('cached_col_' + colId);
      if (cached) {
        const currentOpenid = app.globalData.openid || wx.getStorageSync('openid');
        const isOwner = Boolean(
          cached.openid && 
          cached.openid === currentOpenid && 
          cached.openid !== 'official' && 
          cached.openid !== 'system' && 
          !cached.is_public
        );
        // 列表接口只返回最多 4 条 preview_items，不能当成详情全集渲染。
        // 详情页必须等待 /detail 返回完整 items，避免数量与内容不一致。
        delete cached.items;
        this.setData({
          collection: cached,
          isOwner: isOwner,
          detailLoading: true,
          detailError: false
        });
        if (cached.title) {
          wx.setNavigationBarTitle({ title: cached.title });
        }
      }

      this.fetchDetail(colId);
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
    const requestId = (this._detailRequestId || 0) + 1;
    this._detailRequestId = requestId;
    const hasCached = Boolean(this.data.collection && this.data.collection.title);
    this.setData({ detailLoading: true, detailError: false });
    if (!hasCached) {
      wx.showLoading({ title: '极速载入中...' });
    }
    app.request({
      url: `${app.globalData.baseURL}/api/collection/detail?collection_id=${encodeURIComponent(id)}&_ts=${Date.now()}`,
      method: 'GET',
      success: (res) => {
        if (requestId !== this._detailRequestId) return;
        if (!hasCached) wx.hideLoading();
        if (res.data && res.data.data) {
          const col = res.data.data;
          const currentOpenid = app.globalData.openid || wx.getStorageSync('openid');
          const isOwner = Boolean(
            col.openid && 
            col.openid === currentOpenid && 
            col.openid !== 'official' && 
            col.openid !== 'system' && 
            !col.is_public
          );

          // 处理条目图片绝对路径与极速缩略图 thumb_url
          const items = Array.isArray(col.items) ? col.items : [];
          col.items = items.map((item, index) => {
            let fullUrl = item.gif_url || '';
            if (fullUrl.startsWith('/')) {
              fullUrl = `${app.globalData.baseURL}${fullUrl}`;
            }
            let thumbUrl = item.thumb_url || item.gif_url || '';
            if (thumbUrl.startsWith('/')) {
              thumbUrl = `${app.globalData.baseURL}${thumbUrl}`;
            }
            return {
              ...item,
              full_url: fullUrl,
              thumb_url: thumbUrl,
              // 即使历史条目缺少/重复 id，也必须让每条表情拥有独立的 WXML key。
              render_key: `${item.id || item.gif_url || 'item'}-${index}`
            };
          });
          // 详情页以实际返回的完整条目为准，避免沿用列表摘要中的旧 item_count。
          col.item_count = col.items.length;
          this.setData({ 
            collection: col,
            isOwner: isOwner,
            detailLoading: false,
            detailError: false
          });
          wx.setNavigationBarTitle({ title: col.title || '表情包合集' });
        } else {
          this.setData({ detailLoading: false, detailError: true });
        }
        if (cb) cb();
      },
      fail: () => {
        if (requestId !== this._detailRequestId) return;
        if (!hasCached) wx.hideLoading();
        this.setData({ detailLoading: false, detailError: true });
        wx.showToast({ title: '加载失败', icon: 'none' });
        if (cb) cb();
      }
    });
  },

  retryDetail() {
    if (this.data.collectionId) this.fetchDetail(this.data.collectionId);
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

  goToMakeSame(e) {
    const item = e.currentTarget.dataset.item || {};
    const colId = (this.data.collection && this.data.collection.collection_id) || '';
    let tplId = 'kiss';
    if (colId.includes('battle')) tplId = 'battle_chibi';
    else if (colId.includes('worker')) tplId = 'slack_worker';
    else if (colId.includes('pet')) tplId = 'pet_idle';
    else if (colId.includes('dance')) tplId = 'heart_dance';
    else if (colId.includes('custom')) tplId = 'custom';

    wx.setStorageSync('preselect_tpl', {
      id: tplId,
      caption: item.title || ''
    });
    wx.switchTab({ url: '/pages/index/index' });
  },

  deleteItem(e) {
    if (!this.data.isOwner) {
      wx.showToast({ title: '精选广场官方表情不可删除', icon: 'none' });
      return;
    }

    const itemId = e.currentTarget.dataset.id;
    if (!itemId) return;
    const openid = app.globalData.openid || wx.getStorageSync('openid');

    wx.showModal({
      title: '确认移除',
      content: '确定要从该合集中移除这张表情吗？',
      confirmColor: '#ef4444',
      success: (mRes) => {
        if (mRes.confirm) {
          wx.showLoading({ title: '正在移除...' });
          app.request({
            url: `${app.globalData.baseURL}/api/collection/item/delete`,
            method: 'POST',
            data: { item_id: itemId, openid: openid },
            success: (res) => {
              wx.hideLoading();
              if (res.data && res.data.success) {
                wx.showToast({ title: '已移除', icon: 'success' });
                this.fetchDetail(this.data.collectionId);
              } else {
                wx.showToast({ title: (res.data && res.data.detail) || '移除失败', icon: 'none' });
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
    if (!this.data.isOwner) {
      wx.showToast({ title: '精选广场官方合集不可删除', icon: 'none' });
      return;
    }

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
          app.request({
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
