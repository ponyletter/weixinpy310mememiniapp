App({
  globalData: {
    // 微信规范强制使用 HTTPS 域名
    baseURL: 'https://meme.tg-cc755.cn',
    userInfo: null,
    openid: '',
    quota: 0,
    isVip: false,
    inviterCode: ''
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
    if (cachedOpenid) {
      that.globalData.openid = cachedOpenid;
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
                wx.setStorageSync('openid', user.openid);
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
    wx.request({
      url: `${that.globalData.baseURL}/api/user/profile?openid=${openid || that.globalData.openid}`,
      method: 'GET',
      success: (res) => {
        if (res.data && res.data.success) {
          const user = res.data.user;
          that.globalData.userInfo = user;
          that.globalData.quota = user.total_quota || 0;
          that.globalData.isVip = user.is_vip === 1;
          if (callback) callback(user);
        }
      }
    });
  },

  // 微信虚拟支付 2.0 统一下单与收银台调用
  invokeVirtualPayment(packageId, onSuccess, onFail) {
    const that = this;
    if (!that.globalData.openid) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }

    wx.showLoading({ title: '正在拉起收银台...' });
    wx.request({
      url: `${that.globalData.baseURL}/api/pay/create-order`,
      method: 'POST',
      data: {
        openid: that.globalData.openid,
        package_id: packageId
      },
      success: (res) => {
        wx.hideLoading();
        if (res.data && res.data.success) {
          const payData = res.data.data;
          const params = payData.payment_params;

          // 调用官方微信小程序虚拟支付能力
          if (wx.requestVirtualPayment) {
            wx.requestVirtualPayment({
              signData: params.signData,
              paySig: params.paySig,
              signature: params.signature,
              mode: params.mode,
              success: () => {
                wx.showToast({ title: '充值成功！', icon: 'success' });
                that.fetchUserProfile();
                if (onSuccess) onSuccess();
              },
              fail: (err) => {
                console.log("真机虚拟支付回调/取消:", err);
                // 如果在开发者工具模拟器环境，提示可使用测试充值
                if (err.errMsg && (err.errMsg.includes("-15001") || err.errMsg.includes("not support"))) {
                  wx.showModal({
                    title: '开发者环境提示',
                    content: '当前环境未挂载金融收银台。是否直接模拟完成 1 元/5 元测试支付？',
                    confirmText: '模拟完成',
                    success: (mRes) => {
                      if (mRes.confirm) {
                        wx.request({
                          url: `${that.globalData.baseURL}/api/pay/mock-pay`,
                          method: 'POST',
                          data: { order_id: payData.order_id },
                          success: () => {
                            wx.showToast({ title: '模拟支付成功！', icon: 'success' });
                            that.fetchUserProfile();
                            if (onSuccess) onSuccess();
                          }
                        });
                      }
                    }
                  });
                } else if (onFail) {
                  onFail(err);
                }
              }
            });
          } else {
            // 兼容低版本
            wx.showModal({
              title: '提示',
              content: '当前微信版本过低，请升级微信后再发起充值'
            });
          }
        } else {
          wx.showToast({ title: res.data.detail || '下单失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '网络连接超时', icon: 'none' });
      }
    });
  }
});
