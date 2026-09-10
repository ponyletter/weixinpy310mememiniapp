const app = getApp();

Page({
  data: {
    user: {},
    packages: [],
    redeemCode: ''
  },

  onLoad() {
    this.fetchData();
    this.fetchPackages();
  },

  onShow() {
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
      this.setData({ user });
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
          this.setData({ packages: res.data.packages });
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

  goToOrderCenter() {
    wx.navigateTo({
      url: '/pages/order/order'
    });
  },

  onShareAppMessage() {
    const code = this.data.user.invite_code || '';
    return {
      title: '送你10次免费AI表情包制作额度，一键生成微信动图！',
      path: `/pages/index/index?inviter=${code}`,
      imageUrl: ''
    };
  }
});
