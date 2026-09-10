const app = getApp();

Page({
  data: {
    user: {},
    packages: [
      { package_id: 'item_100', name: '尝鲜包 (20次)', price: 100, price_yuan: '1', quota: 20, unit_price: '0.05', badge_text: '超低破冰' },
      { package_id: 'item_500', name: '超值包 (120次)', price: 500, price_yuan: '5', quota: 120, unit_price: '0.04', badge_text: '爆款推荐' },
      { package_id: 'item_990', name: '尊享包 (300次/VIP)', price: 990, price_yuan: '9.9', quota: 300, unit_price: '0.03', badge_text: '年度特惠' }
    ],
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
    }
  },

  onLoad() {
    this.setData({ config: app.getGifConfig() });
    this.fetchData();
    this.fetchPackages();
  },

  onShow() {
    this.setData({ config: app.getGifConfig() });
    this.fetchData();
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

  buyPackage(e) {
    const pkgId = e.currentTarget.dataset.id;
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
          wx.showToast({ title: res.data.error || '今日已签到', icon: 'none' });
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
          wx.showToast({ title: res.data.error || '兑换失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '网络超时', icon: 'none' });
      }
    });
  },

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
