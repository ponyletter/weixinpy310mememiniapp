const app = getApp();

Page({
  data: {
    user: {},
    packages: [
      { package_id: 'meme_100', name: '尝鲜包 (20次)', price: 100, price_yuan: '1', quota: 20, unit_price: '0.05', badge_text: '超低破冰' },
      { package_id: 'meme_500', name: '超值包 (120次)', price: 500, price_yuan: '5', quota: 120, unit_price: '0.04', badge_text: '爆款推荐' },
      { package_id: 'meme_990', name: '尊享包 (300次/VIP)', price: 990, price_yuan: '9.9', quota: 300, unit_price: '0.03', badge_text: '年度特惠' }
    ],
    selectedPackageId: 'meme_500',
    redeemCode: '',
    showConfigModal: false,
    showFaqModal: false,
    showAgreementModal: false,
    config: {
      fastMode: true,
      resolution: '240x240',
      fps: 8,
      smartCompress: true,
      loopCount: 0
    },

    // 商务与开发者交流弹窗
    showConsultModal: false,
    contactWeChat: {
      name: '表情包制作 · 开发者微信',
      wechatId: 'Mykahr'
    },

    // 个人资料编辑
    showEditModal: false,
    savingProfile: false,
    genderOptions: ['保密', '男', '女'],
    genderIndex: 0,
    editForm: {
      nickname: '',
      avatar_url: '',
      gender: '保密',
      birthday: '',
      bio: ''
    },
    bioLength: 0,

    // 历史创作记录 / 我的相册
    showHistoryModal: false,
    historyLoading: false,
    historyList: [],

    // 历史存入合集
    showHistoryColModal: false,
    userCollections: [],
    targetColId: '',
    selectedHistoryItem: null
  },

  onLoad() {
    this.setData({ config: app.getGifConfig() });
    this.fetchData();
    this.fetchPackages();
  },

  onShow() {
    this.setData({ config: app.getGifConfig() });
    this.fetchData(() => {
      this.fetchHistorySilently();
    });
  },

  onPullDownRefresh() {
    this.fetchData(() => {
      this.fetchPackages();
      wx.stopPullDownRefresh();
    });
  },

  fetchData(cb) {
    app.fetchUserProfile(null, (user) => {
      if (user) {
        user.display_id = user.openid ? user.openid.slice(-8) : '未登录';
      }
      this.setData({ user: user || {} });
      if (cb) cb();
    });
  },

  refreshProfile() {
    wx.showLoading({ title: '刷新资产中...' });
    this.fetchData(() => {
      wx.hideLoading();
      wx.showToast({ title: '已同步最新额度', icon: 'success' });
    });
  },

  copyUid() {
    const openid = this.data.user.openid || app.globalData.openid || wx.getStorageSync('openid') || '';
    if (!openid) {
      wx.showToast({ title: '未获取到有效UID', icon: 'none' });
      return;
    }
    wx.setClipboardData({
      data: openid,
      success: () => {
        wx.showToast({ title: 'UID已复制', icon: 'success' });
      }
    });
  },

  goToCollectionTab() {
    wx.switchTab({
      url: '/pages/collection/collection'
    });
  },

  openConsultModal() {
    this.setData({ showConsultModal: true });
  },

  closeConsultModal() {
    this.setData({ showConsultModal: false });
  },

  copyWeChatId() {
    const wid = (this.data.contactWeChat && this.data.contactWeChat.wechatId) || 'Mykahr';
    wx.setClipboardData({
      data: wid,
      success: () => {
        wx.showModal({
          title: '复制成功 🎉',
          content: `开发者微信号【${wid}】已复制到剪贴板，请前往微信搜索添加好友！`,
          showCancel: false,
          confirmText: '我知道了'
        });
      }
    });
  },

  copyAuthorWechat() {
    this.openConsultModal();
  },

  // ---------------- 个人资料编辑 ----------------
  openEditModal() {
    const u = this.data.user || {};
    const gIndex = this.data.genderOptions.indexOf(u.gender || '保密');
    this.setData({
      showEditModal: true,
      genderIndex: gIndex >= 0 ? gIndex : 0,
      editForm: {
        nickname: u.nickname || '微信用户',
        avatar_url: u.avatar_url || '',
        gender: u.gender || '保密',
        birthday: u.birthday || '',
        bio: u.bio || ''
      },
      bioLength: (u.bio || '').length
    });
  },

  closeEditModal() {
    this.setData({ showEditModal: false });
  },

  onChooseAvatar(e) {
    const tempUrl = e.detail.avatarUrl;
    if (!tempUrl) return;

    // 上传到后端服务器保存
    wx.showLoading({ title: '正在上传头像...' });
    wx.uploadFile({
      url: `${app.globalData.baseURL}/api/user/upload-avatar`,
      filePath: tempUrl,
      name: 'file',
      success: (res) => {
        wx.hideLoading();
        try {
          const data = JSON.parse(res.data);
          if (data && data.avatar_url) {
            const finalUrl = data.avatar_url.startsWith('http') ? data.avatar_url : `${app.globalData.baseURL}${data.avatar_url}`;
            this.setData({ 'editForm.avatar_url': finalUrl });
            wx.showToast({ title: '头像上传成功', icon: 'success' });
          } else {
            this.setData({ 'editForm.avatar_url': tempUrl });
          }
        } catch (err) {
          this.setData({ 'editForm.avatar_url': tempUrl });
        }
      },
      fail: () => {
        wx.hideLoading();
        this.setData({ 'editForm.avatar_url': tempUrl });
      }
    });
  },

  onNicknameBlur(e) {
    const val = (e.detail.value || '').trim();
    if (val) {
      this.setData({ 'editForm.nickname': val });
    }
  },

  onNicknameInput(e) {
    this.setData({ 'editForm.nickname': e.detail.value });
  },

  onGenderChange(e) {
    const idx = Number(e.detail.value);
    this.setData({
      genderIndex: idx,
      'editForm.gender': this.data.genderOptions[idx]
    });
  },

  onBirthdayChange(e) {
    this.setData({ 'editForm.birthday': e.detail.value });
  },

  onBioInput(e) {
    const val = e.detail.value || '';
    this.setData({ 
      'editForm.bio': val,
      bioLength: val.length
    });
  },

  saveProfile() {
    const form = this.data.editForm;
    const openid = this.data.user.openid || app.globalData.openid;
    if (!openid) {
      wx.showToast({ title: '请先完成授权', icon: 'none' });
      return;
    }

    this.setData({ savingProfile: true });
    wx.request({
      url: `${app.globalData.baseURL}/api/user/update-profile`,
      method: 'POST',
      data: {
        openid: openid,
        nickname: form.nickname,
        avatar_url: form.avatar_url,
        bio: form.bio,
        gender: form.gender,
        birthday: form.birthday
      },
      success: (res) => {
        this.setData({ savingProfile: false });
        if (res.data && res.data.success) {
          wx.showToast({ title: '资料更新成功', icon: 'success' });
          this.setData({ showEditModal: false });
          this.fetchData();
        } else {
          wx.showToast({ title: (res.data && res.data.error) || '保存失败', icon: 'none' });
        }
      },
      fail: () => {
        this.setData({ savingProfile: false });
        wx.showToast({ title: '网络连接超时', icon: 'none' });
      }
    });
  },

  // ---------------- 历史创作记录 / 我的相册 ----------------
  openHistoryModal() {
    const hasData = this.data.historyList && this.data.historyList.length > 0;
    this.setData({
      showHistoryModal: true,
      historyLoading: !hasData
    });
    this.fetchHistory();
  },

  closeHistoryModal() {
    this.setData({ showHistoryModal: false });
  },

  fetchHistorySilently() {
    const openid = this.data.user.openid || app.globalData.openid || '';
    if (!openid) return;
    this.fetchHistory();
  },

  fetchHistory() {
    const openid = this.data.user.openid || app.globalData.openid || '';
    if (!openid) {
      this.setData({ historyLoading: false });
      return;
    }
    wx.request({
      url: `${app.globalData.baseURL}/api/meme/history`,
      method: 'GET',
      data: { openid: openid },
      success: (res) => {
        this.setData({ historyLoading: false });
        if (res.data && res.data.data) {
          const list = res.data.data
            .filter(item => item.gif_url)
            .map(item => {
              let fullUrl = item.gif_url;
              if (fullUrl && !fullUrl.startsWith('http')) {
                fullUrl = `${app.globalData.baseURL}${fullUrl}`;
              }
              let thumbUrl = item.thumb_url || item.gif_url;
              if (thumbUrl && !thumbUrl.startsWith('http')) {
                thumbUrl = `${app.globalData.baseURL}${thumbUrl}`;
              }
              return {
                ...item,
                full_gif_url: fullUrl,
                thumb_url: thumbUrl,
                display_title: item.display_title || item.text_bottom || '精选动图',
                created_at: item.created_at ? item.created_at.slice(0, 16) : '近期'
              };
            });
          this.setData({ historyList: list });
        }
      },
      fail: () => {
        this.setData({ historyLoading: false });
      }
    });
  },

  previewHistoryGif(e) {
    const url = e.currentTarget.dataset.url;
    if (url) {
      wx.previewImage({
        urls: [url],
        current: url
      });
    }
  },

  saveHistoryToAlbum(e) {
    const url = e.currentTarget.dataset.url;
    if (!url) return;
    wx.showLoading({ title: '下载中...' });
    wx.downloadFile({
      url: url,
      success: (res) => {
        if (res.statusCode === 200) {
          wx.saveImageToPhotosAlbum({
            filePath: res.tempFilePath,
            success: () => {
              wx.hideLoading();
              wx.showToast({ title: '已保存至手机相册', icon: 'success' });
            },
            fail: (err) => {
              wx.hideLoading();
              if (err.errMsg && err.errMsg.includes('auth deny')) {
                wx.showModal({
                  title: '需要相册权限',
                  content: '请在右上角设置中开启相册写入权限',
                  confirmText: '去开启',
                  success: (setRes) => {
                    if (setRes.confirm) wx.openSetting();
                  }
                });
              } else {
                wx.showToast({ title: '保存失败', icon: 'none' });
              }
            }
          });
        } else {
          wx.hideLoading();
          wx.showToast({ title: '下载失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '网络连接超时', icon: 'none' });
      }
    });
  },

  openHistorySaveColModal(e) {
    const item = e.currentTarget.dataset.item;
    const openid = this.data.user.openid || app.globalData.openid || '';
    wx.showLoading({ title: '加载合集中...' });
    wx.request({
      url: `${app.globalData.baseURL}/api/collection/list`,
      method: 'GET',
      data: { openid: openid },
      success: (res) => {
        wx.hideLoading();
        let cols = (res.data && res.data.data) || [];
        if (cols.length === 0) {
          // 自动新建默认合集
          wx.request({
            url: `${app.globalData.baseURL}/api/collection/create`,
            method: 'POST',
            data: { openid: openid, title: '我的精选表情', description: '默认表情合集' },
            success: (cRes) => {
              if (cRes.data && cRes.data.data) {
                const defCol = cRes.data.data;
                this.setData({
                  userCollections: [defCol],
                  targetColId: defCol.collection_id,
                  selectedHistoryItem: item,
                  showHistoryColModal: true
                });
              }
            }
          });
        } else {
          this.setData({
            userCollections: cols,
            targetColId: cols[0].collection_id,
            selectedHistoryItem: item,
            showHistoryColModal: true
          });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '加载合集失败', icon: 'none' });
      }
    });
  },

  closeHistoryColModal() {
    this.setData({ showHistoryColModal: false });
  },

  selectTargetCol(e) {
    this.setData({ targetColId: e.currentTarget.dataset.id });
  },

  confirmSaveHistoryToCol() {
    const colId = this.data.targetColId;
    const item = this.data.selectedHistoryItem;
    if (!colId || !item) {
      wx.showToast({ title: '请选择合集', icon: 'none' });
      return;
    }

    wx.showLoading({ title: '正在存入...' });
    wx.request({
      url: `${app.globalData.baseURL}/api/collection/add-item`,
      method: 'POST',
      data: {
        collection_id: colId,
        gif_url: item.full_gif_url,
        title: item.display_title || item.text_bottom || '精选动图'
      },
      success: (res) => {
        wx.hideLoading();
        if (res.data && res.data.success) {
          this.setData({ showHistoryColModal: false });
          wx.showToast({ title: '存入合集成功！', icon: 'success' });
        } else {
          wx.showToast({ title: (res.data && res.data.error) || '存入失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '网络超时', icon: 'none' });
      }
    });
  },

  deleteHistoryItem(e) {
    const taskId = e.currentTarget.dataset.id;
    if (!taskId) return;
    const openid = this.data.user.openid || app.globalData.openid || wx.getStorageSync('openid') || '';

    wx.showModal({
      title: '确认删除作品',
      content: '确定要将这张动图从作品相册中删除吗？删除后不可恢复。',
      confirmColor: '#ef4444',
      success: (mRes) => {
        if (mRes.confirm) {
          wx.showLoading({ title: '正在删除...' });
          wx.request({
            url: `${app.globalData.baseURL}/api/meme/delete`,
            method: 'POST',
            data: { task_id: taskId, openid: openid },
            success: (res) => {
              wx.hideLoading();
              if (res.data && (res.data.success || res.data.code === 0)) {
                const newList = this.data.historyList.filter(item => item.task_id !== taskId);
                const updatedUser = { 
                  ...this.data.user, 
                  works_count: newList.length, 
                  total_generated: newList.length 
                };
                this.setData({ 
                  historyList: newList,
                  user: updatedUser
                });
                wx.showToast({ title: '作品已删除', icon: 'success' });
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

  // ---------------- 支付与兑换 ----------------
  fetchPackages() {
    wx.request({
      url: `${app.globalData.baseURL}/api/pay/goods`,
      method: 'GET',
      success: (res) => {
        if (res.data && res.data.packages) {
          const packages = res.data.packages.map(pkg => {
            const priceYuan = (pkg.price / 100).toString();
            const unitPrice = (pkg.price / 100 / (pkg.quota || 1)).toFixed(2);
            return {
              ...pkg,
              price_yuan: priceYuan,
              unit_price: unitPrice
            };
          });
          this.setData({ packages });
        }
      }
    });
  },

  selectPackage(e) {
    const pkgId = e.currentTarget.dataset.id;
    if (pkgId) {
      this.setData({ selectedPackageId: pkgId });
    }
  },

  buyPackage(e) {
    const pkgId = e.currentTarget.dataset.id || this.data.selectedPackageId;
    app.invokeVirtualPayment(pkgId, () => {
      this.fetchData();
    });
  },

  handleDailyCheckin() {
    if (!this.data.user.openid) return;
    wx.showLoading({ title: '签到中...' });
    wx.request({
      url: `${app.globalData.baseURL}/api/user/checkin`,
      method: 'POST',
      data: { openid: this.data.user.openid },
      success: (res) => {
        wx.hideLoading();
        if (res.data && res.data.success) {
          wx.showToast({ title: '签到成功 +3 次！', icon: 'success' });
          this.fetchData();
        } else {
          wx.showToast({ title: (res.data && res.data.error) || '今日已签到', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '网络超时', icon: 'none' });
      }
    });
  },

  copyInviteCode() {
    if (!this.data.user.invite_code) return;
    wx.setClipboardData({
      data: this.data.user.invite_code,
      success: () => {
        wx.showToast({ title: '邀请码已复制', icon: 'success' });
      }
    });
  },

  onInputRedeem(e) {
    this.setData({ redeemCode: e.detail.value });
  },

  submitRedeem() {
    const code = this.data.redeemCode.trim();
    if (!code) {
      wx.showToast({ title: '请输入兑换码', icon: 'none' });
      return;
    }

    // 前端防呆校验：不能使用自己的邀请码
    const myInvite = (this.data.user.invite_code || '').trim().toUpperCase();
    if (myInvite && code.toUpperCase() === myInvite) {
      wx.showModal({
        title: '提示',
        content: '不能使用自己的邀请码哦！快把邀请码分享给微信好友吧~',
        showCancel: false,
        confirmText: '我知道了'
      });
      return;
    }

    wx.showLoading({ title: '正在兑换...' });
    wx.request({
      url: `${app.globalData.baseURL}/api/user/redeem`,
      method: 'POST',
      data: {
        openid: this.data.user.openid,
        code: code
      },
      success: (res) => {
        wx.hideLoading();
        if (res.data && res.data.success) {
          wx.showToast({ title: res.data.message || '兑换成功！', icon: 'success' });
          this.setData({ redeemCode: '' });
          this.fetchData();
        } else {
          wx.showToast({ title: (res.data && res.data.error) || '兑换失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '网络超时', icon: 'none' });
      }
    });
  },

  // ---------------- 动图专属参数配置 ----------------
  openConfigModal() {
    this.setData({
      showConfigModal: true,
      config: app.getGifConfig()
    });
  },

  closeConfigModal() {
    this.setData({ showConfigModal: false });
  },

  onToggleFastMode(e) {
    this.setData({ ['config.fastMode']: e.detail.value });
  },

  setResolution(e) {
    const val = e.currentTarget.dataset.val;
    this.setData({ ['config.resolution']: val });
  },

  setFps(e) {
    const val = Number(e.currentTarget.dataset.val);
    this.setData({ ['config.fps']: val });
  },

  onToggleSmartCompress(e) {
    this.setData({ ['config.smartCompress']: e.detail.value });
  },

  setLoopCount(e) {
    const val = Number(e.currentTarget.dataset.val);
    this.setData({ ['config.loopCount']: val });
  },

  resetConfig() {
    const defaultCfg = {
      fastMode: true,
      resolution: '240x240',
      fps: 8,
      smartCompress: true,
      loopCount: 0
    };
    this.setData({ config: defaultCfg });
    app.setGifConfig(defaultCfg);
    wx.showToast({ title: '已恢复默认设置', icon: 'success' });
  },

  saveAndCloseConfig() {
    app.setGifConfig(this.data.config);
    this.setData({ showConfigModal: false });
    wx.showToast({ title: '配置已更新保存', icon: 'success' });
  },

  openFaqModal() {
    this.setData({ showFaqModal: true });
  },

  closeFaqModal() {
    this.setData({ showFaqModal: false });
  },

  openAgreementModal() {
    this.setData({ showAgreementModal: true });
  },

  closeAgreementModal() {
    this.setData({ showAgreementModal: false });
  },

  stopBubble() {},

  goToOrderCenter() {
    wx.navigateTo({
      url: '/pages/order/order'
    });
  },

  onShareAppMessage() {
    const code = this.data.user.invite_code || '';
    return {
      title: '送你10次免费动图制作额度，一键生成微信专属表情包！',
      path: `/pages/index/index?inviter=${code}`,
      imageUrl: ''
    };
  }
});
