const app = getApp();

Page({
  data: {
    collectionId: '',
    collection: {},
    displayItems: [],
    searchKeyword: '',
    isOwner: false,
    detailLoading: false,
    detailError: false,
    showRenameModal: false,
    targetRenameItem: null,
    renameTitle: '',
    showMoveModal: false,
    targetMoveItem: null,
    otherCollections: []
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
              render_key: `${item.id || item.gif_url || 'item'}-${index}`
            };
          });
          col.item_count = col.items.length;
          this._allItems = col.items;
          this.setData({ 
            collection: col,
            isOwner: isOwner,
            detailLoading: false,
            detailError: false
          });
          this.filterItems(this.data.searchKeyword);
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

  // --- 搜索与过滤 ---
  onSearchInput(e) {
    const kw = (e.detail.value || '').trim().toLowerCase();
    this.setData({ searchKeyword: kw });
    this.filterItems(kw);
  },

  clearSearch() {
    this.setData({ searchKeyword: '' });
    this.filterItems('');
  },

  filterItems(kw) {
    const all = this._allItems || [];
    if (!kw) {
      this.setData({ displayItems: all });
    } else {
      const filtered = all.filter(it => (it.title || '').toLowerCase().includes(kw));
      this.setData({ displayItems: filtered });
    }
  },

  // --- 排序上移与下移 ---
  moveItemUp(e) {
    const id = e.currentTarget.dataset.id;
    const items = [...(this.data.collection.items || [])];
    const idx = items.findIndex(it => it.id === id);
    if (idx <= 0) return;
    const temp = items[idx];
    items[idx] = items[idx - 1];
    items[idx - 1] = temp;
    this.updateAndSyncOrder(items);
  },

  moveItemDown(e) {
    const id = e.currentTarget.dataset.id;
    const items = [...(this.data.collection.items || [])];
    const idx = items.findIndex(it => it.id === id);
    if (idx < 0 || idx >= items.length - 1) return;
    const temp = items[idx];
    items[idx] = items[idx + 1];
    items[idx + 1] = temp;
    this.updateAndSyncOrder(items);
  },

  updateAndSyncOrder(newItems) {
    const col = { ...this.data.collection, items: newItems };
    this._allItems = newItems;
    this.setData({ collection: col });
    this.filterItems(this.data.searchKeyword);

    const openid = app.globalData.openid || wx.getStorageSync('openid');
    const itemIds = newItems.map(it => it.id);
    app.request({
      url: `${app.globalData.baseURL}/api/collection/item/reorder`,
      method: 'POST',
      data: {
        collection_id: this.data.collectionId,
        item_ids: itemIds,
        openid: openid
      },
      success: (res) => {
        if (res.data && res.data.success) {
          wx.showToast({ title: '排序已更新', icon: 'success', duration: 800 });
        }
      }
    });
  },

  // --- 修改表情备注/改名 ---
  openRenameModal(e) {
    const item = e.currentTarget.dataset.item;
    this.setData({
      showRenameModal: true,
      targetRenameItem: item,
      renameTitle: item.title || ''
    });
  },

  closeRenameModal() {
    this.setData({ showRenameModal: false, targetRenameItem: null });
  },

  onInputRenameTitle(e) {
    this.setData({ renameTitle: e.detail.value });
  },

  confirmRename() {
    const item = this.data.targetRenameItem;
    if (!item) return;
    const newTitle = (this.data.renameTitle || '').trim();
    if (!newTitle) {
      wx.showToast({ title: '备注不能为空', icon: 'none' });
      return;
    }
    const openid = app.globalData.openid || wx.getStorageSync('openid');
    wx.showLoading({ title: '正在保存...' });
    app.request({
      url: `${app.globalData.baseURL}/api/collection/item/rename`,
      method: 'POST',
      data: {
        item_id: item.id,
        title: newTitle,
        openid: openid
      },
      success: (res) => {
        wx.hideLoading();
        if (res.data && res.data.success) {
          const items = (this.data.collection.items || []).map(it => it.id === item.id ? { ...it, title: newTitle } : it);
          this._allItems = items;
          this.setData({
            'collection.items': items,
            showRenameModal: false
          });
          this.filterItems(this.data.searchKeyword);
          wx.showToast({ title: '修改成功', icon: 'success' });
        } else {
          wx.showToast({ title: (res.data && res.data.detail) || '修改失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '网络连接超时', icon: 'none' });
      }
    });
  },

  // --- 移动表情到其他合集 ---
  openMoveModal(e) {
    const item = e.currentTarget.dataset.item;
    const openid = app.globalData.openid || wx.getStorageSync('openid');
    wx.showLoading({ title: '加载合集中...' });
    app.request({
      url: `${app.globalData.baseURL}/api/collection/my?openid=${openid}`,
      method: 'GET',
      success: (res) => {
        wx.hideLoading();
        const list = (res.data && res.data.data) || [];
        const others = list.filter(c => c.collection_id !== this.data.collectionId);
        if (others.length === 0) {
          wx.showModal({
            title: '暂无其他合集',
            content: '你还没有其他自建合集，可在首页生成动图并存入时新建一个合集！',
            showCancel: false
          });
          return;
        }
        this.setData({
          showMoveModal: true,
          targetMoveItem: item,
          otherCollections: others
        });
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '网络连接异常', icon: 'none' });
      }
    });
  },

  closeMoveModal() {
    this.setData({ showMoveModal: false, targetMoveItem: null });
  },

  confirmMoveTo(e) {
    const targetColId = e.currentTarget.dataset.id;
    const targetTitle = e.currentTarget.dataset.title;
    const item = this.data.targetMoveItem;
    if (!item || !targetColId) return;

    const openid = app.globalData.openid || wx.getStorageSync('openid');
    wx.showLoading({ title: '正在移动...' });
    app.request({
      url: `${app.globalData.baseURL}/api/collection/item/move`,
      method: 'POST',
      data: {
        item_id: item.id,
        target_collection_id: targetColId,
        openid: openid
      },
      success: (res) => {
        wx.hideLoading();
        if (res.data && res.data.success) {
          const items = (this.data.collection.items || []).filter(it => it.id !== item.id);
          this._allItems = items;
          this.setData({
            'collection.items': items,
            'collection.item_count': items.length,
            showMoveModal: false
          });
          this.filterItems(this.data.searchKeyword);
          wx.showToast({ title: `已移至【${targetTitle}】`, icon: 'success' });
        } else {
          wx.showToast({ title: (res.data && res.data.detail) || '移动失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '网络超时', icon: 'none' });
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
