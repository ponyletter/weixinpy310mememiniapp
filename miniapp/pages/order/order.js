const app = getApp();

Page({
  data: {
    orders: []
  },

  onLoad() {
    this.fetchOrders();
  },

  onShow() {
    this.fetchOrders();
  },

  onPullDownRefresh() {
    this.fetchOrders(() => wx.stopPullDownRefresh());
  },

  fetchOrders(cb) {
    const openid = app.globalData.openid || wx.getStorageSync('openid');
    if (!openid) {
      if (cb) cb();
      return;
    }

    wx.showLoading({ title: '加载订单中...' });
    wx.request({
      url: `${app.globalData.baseURL}/api/user/orders?openid=${openid}`,
      method: 'GET',
      success: (res) => {
        wx.hideLoading();
        if (res.data && res.data.orders) {
          this.setData({ orders: res.data.orders });
        }
        if (cb) cb();
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '加载失败', icon: 'none' });
      }
    });
  }
});
