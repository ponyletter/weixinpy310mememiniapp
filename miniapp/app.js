App({
  globalData: {
    // 微信规范强制使用 HTTPS 域名
    baseURL: 'https://meme.tg-cc755.cn',
    userInfo: null,
    openid: '',
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
    const targetOpenid = openid || that.globalData.openid || wx.getStorageSync('openid');
    if (!targetOpenid) {
      // 缓存被清理或未登录，先静默换取 openid 后再获取 profile
      that.silentLogin((user) => {
        if (callback) callback(user);
      });
      return;
    }
    wx.request({
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

  // 微信虚拟支付 2.0 统一下单与收银台调用
  invokeVirtualPayment(packageId, onSuccess, onFail) {
    const that = this;
    const openid = that.globalData.openid || wx.getStorageSync('openid');
    if (!openid) {
      wx.showToast({ title: '正在登录中，请稍候...', icon: 'none' });
      that.silentLogin(() => {
        that.invokeVirtualPayment(packageId, onSuccess, onFail);
      });
      return;
    }
    that.globalData.openid = openid;

    wx.showLoading({ title: '正在拉起收银台...' });
    wx.request({
      url: `${that.globalData.baseURL}/api/pay/create-order`,
      method: 'POST',
      data: {
        openid: openid,
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
                console.warn("微信虚拟支付回调异常/取消:", err);
                const errMsg = (err && (err.errMsg || err.message)) || '';

                // 1. 用户主动取消支付
                if (errMsg.includes("cancel") || errMsg.includes("取消")) {
                  wx.showToast({ title: '已取消支付', icon: 'none' });
                  if (onFail) onFail(err);
                  return;
                }

                // 2. 模拟器环境、电脑开发工具或暂未挂载收银台
                const isDevOrNotSupport = errMsg.includes("-15001") || 
                                          errMsg.includes("not support") || 
                                          errMsg.includes("不支持") || 
                                          errMsg.includes("developer tools") || 
                                          errMsg.includes("system error") ||
                                          errMsg.includes("fail");

                if (isDevOrNotSupport) {
                  wx.showModal({
                    title: '开发者环境提示',
                    content: '检测到当前运行在开发工具或模拟器环境（微信虚拟支付金融收银台需在安卓真机端运行）。\n\n是否直接模拟完成本次额度充值进行流程测试？',
                    confirmText: '模拟完成',
                    cancelText: '取消',
                    success: (mRes) => {
                      if (mRes.confirm) {
                        wx.showLoading({ title: '正在结算...' });
                        wx.request({
                          url: `${that.globalData.baseURL}/api/pay/mock-pay`,
                          method: 'POST',
                          data: { order_id: payData.order_id },
                          success: () => {
                            wx.hideLoading();
                            wx.showToast({ title: '模拟支付成功！', icon: 'success' });
                            that.fetchUserProfile();
                            if (onSuccess) onSuccess();
                          },
                          fail: () => {
                            wx.hideLoading();
                            wx.showToast({ title: '模拟结算失败', icon: 'none' });
                          }
                        });
                      }
                    }
                  });
                } else {
                  // 3. 真机端其它原因（如 iOS 受限或商户号未完成实名绑定）
                  wx.showModal({
                    title: '支付提示',
                    content: `拉起支付遇到问题：${errMsg}。\n\n提示：iOS 设备受苹果政策限制暂不支持小程序虚拟支付，请使用安卓手机体验；或点击下方【邀请好友】免费获赠额度！`,
                    showCancel: false,
                    confirmText: '我知道了'
                  });
                  if (onFail) onFail(err);
                }
              }
            });
          } else {
            // 兼容低版本
            wx.showModal({
              title: '提示',
              content: '当前微信版本过低或基础库不支持虚拟支付，请升级微信后再试。'
            });
          }
        } else {
          wx.showToast({ title: (res.data && res.data.detail) || '下单失败', icon: 'none' });
        }
      },
      fail: (err) => {
        wx.hideLoading();
        wx.showToast({ title: '网络请求失败', icon: 'none' });
        if (onFail) onFail(err);
      }
    });
  }
});
