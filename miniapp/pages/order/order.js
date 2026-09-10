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
  },

  // 取消待付款订单 (类似电商模式)
  onCancelOrder(e) {
    const orderId = e.currentTarget.dataset.id;
    if (!orderId) return;

    wx.showModal({
      title: '取消订单',
      content: '确定要取消该待付款订单吗？',
      confirmText: '确定取消',
      cancelText: '暂不取消',
      confirmColor: '#ef4444',
      success: (res) => {
        if (res.confirm) {
          app.cancelVirtualPayment(orderId, () => {
            this.fetchOrders();
          });
        }
      }
    });
  },

  // 继续支付待付款订单 (类似电商模式)
  onRepayOrder(e) {
    const orderId = e.currentTarget.dataset.id;
    if (!orderId) return;

    app.resumeVirtualPayment(orderId, () => {
      // 支付成功回调：刷新订单列表为已支付
      this.fetchOrders();
    });
  }
});
