const app = getApp();

Page({
  data: {
    activeTab: 'my', // 'my' | 'explore' | 'materials'
    myCollections: [],
    exploreCollections: [],
    showCreateModal: false,
    newTitle: '',
    newDesc: '',
    pendingGifUrl: '',
    currentShareItem: null,

    // 素材库 (5800+ ChineseBQB)
    matCategories: [],
    materialsList: [],
    currentMatCat: 'all',
    matPage: 1,
    matHasMore: true,
    matLoading: false,
    matSearchQuery: '',
    showMatModal: false,
    activeMatItem: {},

    // 搜索未命中智能定制模版库
    memeTemplates: [],
    showCustomMemeModal: false,
    currentTpl: null,
    customCaption: '',
    customRenderedUrl: '',
    customRendering: false
  },

  onLoad(options) {
    if (options && options.add_gif) {
      this.setData({
        pendingGifUrl: decodeURIComponent(options.add_gif)
      });
      wx.showToast({ title: '请选择存入的合集', icon: 'none' });
    }
    this.fetchData();
    this.fetchMemeTemplates();
  },

  onShow() {
    const pendingGif = wx.getStorageSync('pending_add_gif');
    if (pendingGif) {
      wx.removeStorageSync('pending_add_gif');
      this.setData({
        pendingGifUrl: pendingGif,
        activeTab: 'my'
      });
      wx.showToast({ title: '请点击合集卡片存入表情', icon: 'none', duration: 2500 });
    }
    this.fetchData();
  },

  onPullDownRefresh() {
    if (this.data.activeTab === 'materials') {
      this.fetchMaterialsList(this.data.currentMatCat, 1, false, () => wx.stopPullDownRefresh());
    } else {
      this.fetchData(() => wx.stopPullDownRefresh());
    }
  },

  switchTab(e) {
    const tab = e.currentTarget.dataset.tab;
    this.setData({ activeTab: tab });
    if (tab === 'materials') {
      if (!this.data.materialsList || this.data.materialsList.length === 0) {
        this.fetchMaterialsCategories();
        this.fetchMaterialsList('all', 1, false);
      }
      if (!this.data.memeTemplates || this.data.memeTemplates.length === 0) {
        this.fetchMemeTemplates();
      }
    }
  },

  fetchData(cb) {
    if (this._fetchInFlight) {
      this._fetchQueued = true;
      this._queuedCallback = cb || this._queuedCallback;
      return;
    }
    this._fetchInFlight = true;
    const openid = app.globalData.openid || wx.getStorageSync('openid');
    // 合集条目会随用户操作变化，GET 请求也显式带版本参数，避免开发者工具/代理复用旧摘要。
    const requestVersion = Date.now();
    let pending = openid ? 2 : 1;
    const finish = () => {
      pending -= 1;
      if (pending > 0) return;
      this._fetchInFlight = false;
      const queued = this._fetchQueued;
      const queuedCallback = this._queuedCallback;
      this._fetchQueued = false;
      this._queuedCallback = null;
      if (cb) cb();
      if (queued) this.fetchData(queuedCallback);
    };
    
    const formatCol = (item) => {
      let cover = item.cover_url || '';
      if (cover && cover.startsWith('/')) {
        cover = app.toAbsoluteUrl(cover);
      }
      let preview_items = (item.preview_items || []).map((p, index) => {
        let thumb = p.thumb_url || p.gif_url || '';
        if (thumb && thumb.startsWith('/')) {
          thumb = app.toAbsoluteUrl(thumb);
        }
        return {
          ...p,
          thumb_url: thumb,
          // 后端历史数据可能缺少 id 或存在重复 id，索引保证预览条目不被 WXML 合并。
          render_key: `${p.id || p.gif_url || 'preview'}-${index}`
        };
      });
      return { ...item, cover_url: cover, preview_items };
    };

    // 获取我的合集
    if (openid) {
      app.request({
        url: `${app.globalData.baseURL}/api/collection/my?openid=${encodeURIComponent(openid)}&_ts=${requestVersion}`,
        method: 'GET',
        success: (res) => {
          if (res.data && res.data.data) {
            const list = res.data.data.map(formatCol);
            this.setData({ myCollections: list });
          }
        },
        complete: finish
      });
    } else {
      finish();
    }

    // 获取精选广场
    app.request({
      url: `${app.globalData.baseURL}/api/collection/explore?_ts=${requestVersion}`,
      method: 'GET',
      success: (res) => {
        if (res.data && res.data.data) {
          const list = res.data.data.map(formatCol);
          this.setData({ exploreCollections: list });
        }
        finish();
      },
      fail: finish
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
        } else {
          wx.showToast({ title: (res.data && (res.data.detail || res.data.error)) || '存入失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '网络超时', icon: 'none' });
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

  // ==================== 素材库 (5800+ ChineseBQB) ====================
  fetchMaterialsCategories() {
    app.request({
      url: `${app.globalData.baseURL}/api/materials/categories`,
      method: 'GET',
      success: (res) => {
        if (res.statusCode === 200 && res.data && res.data.data) {
          this.setData({ matCategories: res.data.data });
        }
      }
    });
  },

  fetchMaterialsList(category, page, append, cb) {
    this.setData({ matLoading: true });
    let url = `${app.globalData.baseURL}/api/materials/list?category=${encodeURIComponent(category || 'all')}&page=${page || 1}&page_size=28`;
    if (this.data.matSearchQuery && this.data.matSearchQuery.trim()) {
      url = `${app.globalData.baseURL}/api/materials/search?q=${encodeURIComponent(this.data.matSearchQuery.trim())}&page=${page || 1}&page_size=28`;
    }

    app.request({
      url: url,
      method: 'GET',
      success: (res) => {
        if (res.statusCode === 200 && res.data && res.data.data) {
          const d = res.data.data;
          const items = d.items || [];
          const newList = append ? this.data.materialsList.concat(items) : items;
          this.setData({
            materialsList: newList,
            matPage: d.page,
            matHasMore: d.has_more,
            currentMatCat: category || 'all'
          });
        }
      },
      complete: () => {
        this.setData({ matLoading: false });
        if (cb) cb();
      }
    });
  },

  loadMoreMaterials() {
    if (!this.data.matHasMore || this.data.matLoading) return;
    this.fetchMaterialsList(this.data.currentMatCat, this.data.matPage + 1, true);
  },

  onSelectMatCat(e) {
    const id = e.currentTarget.dataset.id;
    this.setData({ currentMatCat: id, matSearchQuery: '' });
    this.fetchMaterialsList(id, 1, false);
  },

  onInputMatSearch(e) {
    this.setData({ matSearchQuery: e.detail.value });
  },

  onSearchMaterials() {
    this.fetchMaterialsList(this.data.currentMatCat, 1, false);
  },

  clearMatSearch() {
    this.setData({ matSearchQuery: '' });
    this.fetchMaterialsList(this.data.currentMatCat, 1, false);
  },

  openMaterialAction(e) {
    const item = e.currentTarget.dataset.item;
    this.setData({
      activeMatItem: item,
      showMatModal: true
    });
  },

  closeMatModal() {
    this.setData({ showMatModal: false });
  },

  // 预览素材大图（支持微信原生全屏预览与长按直接转发到聊天）
  previewMaterialImage() {
    const item = this.data.activeMatItem;
    const url = (item && (item.url || item.thumb_url)) || '';
    if (!url) return;
    const absUrl = app.toAbsoluteUrl(url);
    wx.previewImage({
      urls: [absUrl],
      current: absUrl
    });
  },

  // 保存素材图片到手机相册
  saveMaterialToAlbum() {
    const item = this.data.activeMatItem;
    const url = item.url || item.thumb_url;
    if (!url) return;

    wx.showLoading({ title: '正在保存...', mask: true });
    wx.downloadFile({
      url: url,
      success: (res) => {
        if (res.statusCode === 200 && res.tempFilePath) {
          wx.saveImageToPhotosAlbum({
            filePath: res.tempFilePath,
            success: () => {
              wx.hideLoading();
              wx.showToast({ title: '已保存到手机相册！', icon: 'success' });
              this.closeMatModal();
            },
            fail: (err) => {
              wx.hideLoading();
              if (err && err.errMsg && err.errMsg.indexOf('auth') !== -1) {
                wx.showModal({
                  title: '需要相册权限',
                  content: '请在设置中开启相册写入权限',
                  confirmText: '去设置',
                  confirmColor: '#07c160',
                  success: (m) => {
                    if (m.confirm) wx.openSetting();
                  }
                });
              } else {
                wx.showToast({ title: '保存失败', icon: 'none' });
              }
            }
          });
        } else {
          wx.hideLoading();
          wx.showToast({ title: '下载素材失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '网络请求失败', icon: 'none' });
      }
    });
  },

  // 以此图制作 16 款表情
  useMaterialForSticker16() {
    const item = this.data.activeMatItem;
    const url = item.url || item.thumb_url;
    if (!url) return;
    this.closeMatModal();
    wx.navigateTo({
      url: `/pages/sticker16/sticker16?refUrl=${encodeURIComponent(url)}`
    });
  },

  // ==================== 搜索未命中智能定制模版 ====================
  fetchMemeTemplates() {
    app.request({
      url: `${app.globalData.baseURL}/api/materials/templates`,
      method: 'GET',
      success: (res) => {
        if (res.statusCode === 200 && res.data && res.data.data) {
          const list = res.data.data.map(item => ({
            ...item,
            image_url: app.toAbsoluteUrl(item.image_url),
            thumb_url: app.toAbsoluteUrl(item.thumb_url || item.image_url)
          }));
          this.setData({ memeTemplates: list });
        }
      }
    });
  },

  openCustomMemeModal(e) {
    const tpl = e.currentTarget.dataset.tpl;
    const caption = (this.data.matSearchQuery || tpl.default_text || '专属定制').trim();
    this.setData({
      showCustomMemeModal: true,
      currentTpl: tpl,
      customCaption: caption,
      customRenderedUrl: '',
      customRendering: true
    });
    this.renderCustomMeme(tpl.id, caption);
  },

  closeCustomMemeModal() {
    this.setData({ showCustomMemeModal: false });
  },

  onInputCustomCaption(e) {
    this.setData({ customCaption: e.detail.value });
  },

  onConfirmCustomCaption() {
    if (!this.data.customCaption.trim() || !this.data.currentTpl) return;
    this.renderCustomMeme(this.data.currentTpl.id, this.data.customCaption.trim());
  },

  renderCustomMeme(tplId, caption) {
    this.setData({ customRendering: true });
    app.request({
      url: `${app.globalData.baseURL}/api/materials/render-meme`,
      method: 'POST',
      header: { 'content-type': 'application/x-www-form-urlencoded' },
      data: {
        template_id: tplId,
        caption: caption,
        font_size: 28,
        pos: 'bottom',
        color: '#1e293b'
      },
      success: (res) => {
        if (res.statusCode === 200 && res.data && res.data.data) {
          this.setData({
            customRenderedUrl: app.toAbsoluteUrl(res.data.data.image_url),
            customRendering: false
          });
        } else {
          this.setData({ customRendering: false });
          wx.showToast({ title: (res.data && res.data.detail) || '生成失败', icon: 'none' });
        }
      },
      fail: () => {
        this.setData({ customRendering: false });
        wx.showToast({ title: '网络超时', icon: 'none' });
      }
    });
  },

  // 预览定制生成的表情大图（支持长按直接转发到微信聊天）
  previewCustomMemeImage() {
    const url = this.data.customRenderedUrl || (this.data.currentTpl && this.data.currentTpl.image_url);
    if (!url) return;
    const absUrl = app.toAbsoluteUrl(url);
    wx.previewImage({
      urls: [absUrl],
      current: absUrl
    });
  },

  saveCustomMemeToAlbum() {
    const url = this.data.customRenderedUrl;
    if (!url) {
      wx.showToast({ title: '请等待表情绘制完成', icon: 'none' });
      return;
    }
    wx.showLoading({ title: '正在保存相册...' });
    wx.downloadFile({
      url: url,
      success: (res) => {
        wx.hideLoading();
        if (res.statusCode === 200 && res.tempFilePath) {
          wx.saveImageToPhotosAlbum({
            filePath: res.tempFilePath,
            success: () => {
              wx.showToast({ title: '已保存至手机相册！', icon: 'success' });
            },
            fail: () => {
              wx.showToast({ title: '保存失败或缺少权限', icon: 'none' });
            }
          });
        } else {
          wx.showToast({ title: '下载失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '网络请求失败', icon: 'none' });
      }
    });
  },

  saveCustomMemeToCol() {
    const url = this.data.customRenderedUrl;
    if (!url) {
      wx.showToast({ title: '请等待表情绘制完成', icon: 'none' });
      return;
    }
    const openid = app.globalData.openid || wx.getStorageSync('openid');
    const cols = this.data.myCollections || [];
    if (cols.length === 0) {
      // 自动创建默认合集并存入
      wx.showLoading({ title: '正在存入合集...' });
      app.request({
        url: `${app.globalData.baseURL}/api/collection/create`,
        method: 'POST',
        data: {
          openid: openid,
          title: '我的专属表情',
          description: '收录自定义表情'
        },
        success: (cRes) => {
          if (cRes.data && cRes.data.data) {
            this.saveItemToCol(cRes.data.data.collection_id, url);
            this.closeCustomMemeModal();
          } else {
            wx.hideLoading();
            wx.showToast({ title: '存入合集失败', icon: 'none' });
          }
        },
        fail: () => {
          wx.hideLoading();
          wx.showToast({ title: '网络连接超时', icon: 'none' });
        }
      });
    } else {
      // 存入第一个用户合集
      this.saveItemToCol(cols[0].collection_id, url);
      this.closeCustomMemeModal();
    }
  },

  goToRemixMemeMaker() {
    const tpl = this.data.currentTpl;
    const caption = this.data.customCaption;
    this.closeCustomMemeModal();
    let url = `/pages/remix/remix?tab=meme_maker`;
    if (tpl && tpl.id) {
      url += `&tpl=${tpl.id}`;
    }
    if (caption) {
      url += `&caption=${encodeURIComponent(caption)}`;
    }
    wx.navigateTo({ url });
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
