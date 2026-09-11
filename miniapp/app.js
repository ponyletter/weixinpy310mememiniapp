App({
  globalData: {
    // 微信规范强制使用 HTTPS 域名
    baseURL: 'https://meme.tg-cc755.cn',
    userInfo: null,
    openid: '',
    accessToken: '',
    quota: 0,
    isVip: false,
    inviterCode: '',
    // 微信小程序订阅消息模板ID (服务完成通知)
    subscribeTemplateId: 'jsfKx2x1YrKdX600S01pzCcxWe_UjMi_Tx5OtWWfvcs'
  },

  getGifConfig() {
    const cfg = wx.getStorageSync('gif_config');
    if (cfg && typeof cfg === 'object') return cfg;
    return {
      fastMode: true,
      resolution: '240x240',
      fps: 8,
      smartCompress: true,
      loopCount: 0
    };
  },

  setGifConfig(cfg) {
    wx.setStorageSync('gif_config', cfg);
  },

  authHeader(extraHeader) {
    const token = this.globalData.accessToken || wx.getStorageSync('access_token');
    return Object.assign({}, extraHeader || {}, token ? { Authorization: `Bearer ${token}` } : {});
  },

  request(options) {
    return wx.request(Object.assign({}, options, { header: this.authHeader(options.header) }));
  },

  uploadFile(options) {
    return wx.uploadFile(Object.assign({}, options, { header: this.authHeader(options.header) }));
  },

  onLaunch(options) {
    console.log("🚀 小程序启动 options:", options);
    
    // 1. 处理邀请码 (从小程序码或分享卡片携带)
    if (options.query && options.query.inviter) {
      this.globalData.inviterCode = options.query.inviter;
    }

    // 2. 处理聊天素材直接唤起 (chatMaterials 机制)
    if (options.chatMaterial) {
      console.log("🔥 监听到从聊天素材快捷打开:", options.chatMaterial);
      // 跳转至极速二创制作页并带上素材参数
      setTimeout(() => {
        wx.switchTab({
          url: '/pages/remix/remix'
        });
      }, 300);
    }

    // 3. 执行静默登录
    this.silentLogin();
  },

  silentLogin(callback) {
    const that = this;
    // 优先从缓存读取 openid
    const cachedOpenid = wx.getStorageSync('openid');
    const cachedToken = wx.getStorageSync('access_token');
    if (cachedOpenid && cachedToken) {
      that.globalData.openid = cachedOpenid;
      that.globalData.accessToken = cachedToken;
      that.fetchUserProfile(cachedOpenid, callback);
    }

    wx.login({
      success: (res) => {
        if (res.code) {
          wx.request({
            url: `${that.globalData.baseURL}/api/user/login`,
            method: 'POST',
            data: {
              code: res.code,
              inviter_code: that.globalData.inviterCode
            },
            success: (loginRes) => {
              if (loginRes.data && loginRes.data.success) {
                const user = loginRes.data.user;
                that.globalData.openid = user.openid;
                that.globalData.userInfo = user;
                that.globalData.quota = (user.free_quota || 0) + (user.purchased_quota || 0);
                that.globalData.isVip = user.is_vip === 1;
                that.globalData.accessToken = loginRes.data.access_token;
                wx.setStorageSync('openid', user.openid);
                wx.setStorageSync('access_token', loginRes.data.access_token);
                if (callback) callback(user);
              }
            },
            fail: (err) => {
              console.warn("登录接口请求失败，进入离线/Mock模式:", err);
            }
          });
        }
      }
    });
  },

  fetchUserProfile(openid, callback) {
    const that = this;
    const targetOpenid = openid || that.globalData.openid || wx.getStorageSync('openid');
    if (!targetOpenid) {
      // 缓存被清理或未登录，先静默换取 openid 后再获取 profile
      that.silentLogin((user) => {
        if (callback) callback(user);
      });
      return;
    }
    that.request({
      url: `${that.globalData.baseURL}/api/user/profile?openid=${targetOpenid}`,
      method: 'GET',
      success: (res) => {
        if (res.data && res.data.success) {
          const user = res.data.user;
          that.globalData.userInfo = user;
          that.globalData.quota = user.total_quota || 0;
          that.globalData.isVip = user.is_vip === 1;
          if (callback) callback(user);
        } else if (callback) {
          callback(null);
        }
      },
      fail: () => {
        if (callback) callback(null);
      }
    });
  },

  // 支付弹窗成功后，轮询服务端已确认的订单状态。
  // 只有可信回调落库后才刷新额度，避免把前端 success 当成到账凭据。
  waitForPayment(orderId, callback) {
    const that = this;
    let attempts = 0;
    const maxAttempts = 10;
    const poll = () => {
      attempts += 1;
      that.request({
        url: `${that.globalData.baseURL}/api/pay/order-status?order_id=${encodeURIComponent(orderId)}`,
        method: 'GET',
        success: (res) => {
          const data = res.data || {};
          if (data.success && data.paid) {
            callback({ paid: true, status: 'PAID', data: data });
            return;
          }
          if (attempts >= maxAttempts) {
            callback({ paid: false, status: data.status || 'PENDING', data: data });
            return;
          }
          setTimeout(poll, 1200);
        },
        fail: () => {
          if (attempts >= maxAttempts) {
            callback({ paid: false, status: 'PENDING' });
            return;
          }
          setTimeout(poll, 1200);
        }
      });
    };
    poll();
  },

  // 微信虚拟支付 2.0 实际拉起收银台核心方法
  executeVirtualPayment(orderInfo, onSuccess, onFail) {
    const that = this;
    const { order_id, payment_params, is_sandbox } = orderInfo;

    if (wx.requestVirtualPayment && !is_sandbox) {
      wx.requestVirtualPayment({
        signData: payment_params.signData,
        paySig: payment_params.paySig,
        signature: payment_params.signature,
        mode: payment_params.mode,
        success: () => {
          wx.showLoading({ title: '确认支付结果...' });
          that.waitForPayment(order_id, (result) => {
            wx.hideLoading();
            that.fetchUserProfile();
            if (result && result.paid) {
              wx.showToast({ title: '支付成功，额度已到账', icon: 'success' });
            } else {
              wx.showModal({
                title: '支付结果确认中',
                content: '支付平台已返回成功，服务器正在同步订单。请稍后在“订单记录”中刷新查看，额度确认前不会重复扣款。',
                showCancel: false,
                confirmText: '知道了'
              });
            }
            if (onSuccess) onSuccess(result);
          });
        },
        fail: (err) => {
          console.error('wx.requestVirtualPayment 失败详情:', err);
          const errMsg = (err && (err.errMsg || err.message)) || '';
          if (errMsg.includes('cancel') || errMsg.includes('取消')) {
            wx.showToast({ title: '已取消支付', icon: 'none' });
          } else {
            wx.showToast({ title: errMsg || '支付未完成', icon: 'none' });
          }
          if (onFail) onFail(err);
        }
      });
    } else {
      // 沙箱测试模拟
      that.request({
        url: `${that.globalData.baseURL}/api/pay/mock-pay`,
        method: 'POST',
        data: { order_id: order_id },
        success: () => {
          wx.showModal({
            title: '购买成功！',
            content: '制作额度已充入您的账户！',
            showCancel: false
          });
          that.fetchUserProfile();
          if (onSuccess) onSuccess({ paid: true, status: 'PAID' });
        }
      });
    }
  },

  // 微信虚拟支付 2.0 统一下单与收银台调用 (对齐 weixinpy310sphinx_knowledge 成功模式)
  invokeVirtualPayment(packageId, onSuccess, onFail) {
    const that = this;
    const openid = that.globalData.openid || wx.getStorageSync('openid');
    if (!openid) {
      wx.showToast({ title: '正在获取登录态...', icon: 'none' });
      that.silentLogin(() => {
        that.invokeVirtualPayment(packageId, onSuccess, onFail);
      });
      return;
    }
    that.globalData.openid = openid;

    wx.showLoading({ title: '创建订单...' });
    that.request({
      url: `${that.globalData.baseURL}/api/pay/create-order`,
      method: 'POST',
      data: {
        openid: openid,
        package_id: packageId
      },
      success: (res) => {
        wx.hideLoading();
        if (res.data && res.data.success) {
          that.executeVirtualPayment(res.data.data, onSuccess, onFail);
        } else {
          wx.showToast({ title: (res.data && res.data.detail) || '创建订单失败', icon: 'none' });
        }
      },
      fail: (err) => {
        wx.hideLoading();
        wx.showToast({ title: (err && err.errMsg) || '网络请求失败', icon: 'none' });
        if (onFail) onFail(err);
      }
    });
  },

  // 继续支付已有未付款订单 (支持类似电商的继续付款)
  resumeVirtualPayment(orderId, onSuccess, onFail) {
    const that = this;
    const openid = that.globalData.openid || wx.getStorageSync('openid');
    if (!openid) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }

    wx.showLoading({ title: '唤起收银台...' });
    that.request({
      url: `${that.globalData.baseURL}/api/pay/repay-order`,
      method: 'POST',
      data: {
        openid: openid,
        order_id: orderId
      },
      success: (res) => {
        wx.hideLoading();
        if (res.data && res.data.success) {
          that.executeVirtualPayment(res.data.data, onSuccess, onFail);
        } else {
          wx.showToast({ title: (res.data && res.data.detail) || '无法继续支付', icon: 'none' });
          if (onFail) onFail(res.data);
        }
      },
      fail: (err) => {
        wx.hideLoading();
        wx.showToast({ title: (err && err.errMsg) || '网络请求失败', icon: 'none' });
        if (onFail) onFail(err);
      }
    });
  },

  // 取消订单
  cancelVirtualPayment(orderId, onSuccess, onFail) {
    const that = this;
    const openid = that.globalData.openid || wx.getStorageSync('openid');
    if (!openid) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }

    wx.showLoading({ title: '正在取消...' });
    that.request({
      url: `${that.globalData.baseURL}/api/pay/cancel-order`,
      method: 'POST',
      data: {
        openid: openid,
        order_id: orderId
      },
      success: (res) => {
        wx.hideLoading();
        if (res.data && res.data.success) {
          wx.showToast({ title: '订单已取消', icon: 'success' });
          if (onSuccess) onSuccess();
        } else {
          wx.showToast({ title: (res.data && res.data.detail) || '取消失败', icon: 'none' });
          if (onFail) onFail(res.data);
        }
      },
      fail: (err) => {
        wx.hideLoading();
        wx.showToast({ title: (err && err.errMsg) || '网络请求失败', icon: 'none' });
        if (onFail) onFail(err);
      }
    });
  }
});
