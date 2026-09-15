const app = getApp();

Page({
  data: {
    tab: 'video', // 'video' | 'images' | 'caption' | 'stitch' | 'compress' | 'card'
    videoPath: '',
    videoStartTime: 0.0,
    videoDuration: 3.0,
    multiImages: [],
    srcGifPath: '',
    captionText: '',
    isConverting: false,
    remixResultUrl: '',

    // 4. 长图拼接
    stitchImages: [],
    stitchMode: 'vertical', // 'vertical' | 'horizontal' | 'subtitle'
    subtitleRatio: 0.25,

    // 5. 动图与图片瘦身
    compressSrcPath: '',
    compressFileSizeStr: '',
    compressTargetKb: 500,

    // 6. 金句卡片生成器
    cardText: '',
    cardTheme: 'classic', // 'classic' | 'dark' | 'gold' | 'cute' | 'minimal'
    cardTitle: '',
    cardAuthor: '',
    cardFontSize: 32
  },

  onLoad(options) {
    if (options && options.material) {
      // 聊天素材传入
      this.handleIncomingMaterial(options.material);
    }
  },

  switchTab(e) {
    const tab = e.currentTarget.dataset.tab;
    this.setData({
      tab,
      remixResultUrl: '',
      captionText: ''
    });
  },

  onInputCaption(e) {
    this.setData({ captionText: e.detail.value });
  },

  onVideoStartTimeChange(e) {
    this.setData({ videoStartTime: Number(e.detail.value) });
  },

  onVideoDurationChange(e) {
    this.setData({ videoDuration: Number(e.detail.value) });
  },

  // 1. 视频转动图
  chooseVideo() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['video'],
      maxDuration: 30,
      success: (res) => {
        if (res.tempFiles && res.tempFiles.length > 0) {
          this.setData({ videoPath: res.tempFiles[0].tempFilePath });
        }
      }
    });
  },

  clearVideo() {
    this.setData({ videoPath: '' });
  },

  convertVideoToGif() {
    if (!this.data.videoPath) {
      wx.showToast({ title: '请先选择视频', icon: 'none' });
      return;
    }

    this.setData({ isConverting: true });
    wx.showLoading({ title: '正在提取精彩动图...' });

    app.uploadFile({
      url: `${app.globalData.baseURL}/api/convert/video-to-gif`,
      filePath: this.data.videoPath,
      name: 'video',
      formData: {
        caption: this.data.captionText,
        start_time: this.data.videoStartTime || 0.0,
        duration: this.data.videoDuration || 3.0,
        fps: 10,
        width: 240
      },
      success: (res) => {
        wx.hideLoading();
        this.setData({ isConverting: false });
        let data = res.data;
        if (typeof data === 'string') {
          try { data = JSON.parse(data); } catch(e) {}
        }
        if (data && data.success) {
          this.setData({ remixResultUrl: `${app.globalData.baseURL}${data.gif_url}` });
          wx.showToast({ title: '转动图成功！', icon: 'success' });
        } else {
          wx.showToast({ title: (data && data.detail) || '转换失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        this.setData({ isConverting: false });
        wx.showToast({ title: '网络请求超时', icon: 'none' });
      }
    });
  },

  // 2. 多图合成动图
  chooseMultiImages() {
    wx.chooseMedia({
      count: 9 - this.data.multiImages.length,
      mediaType: ['image'],
      success: (res) => {
        if (res.tempFiles && res.tempFiles.length > 0) {
          const newPaths = res.tempFiles.map(f => f.tempFilePath);
          this.setData({
            multiImages: [...this.data.multiImages, ...newPaths]
          });
        }
      }
    });
  },

  removeMultiImage(e) {
    if (this.data.isConverting) return;
    const index = Number(e.currentTarget.dataset.index);
    const multiImages = this.data.multiImages.filter((_, itemIndex) => itemIndex !== index);
    this.setData({ multiImages, remixResultUrl: '' });
  },

  convertImagesToGif() {
    if (this.data.multiImages.length < 2) {
      wx.showToast({ title: '至少需要2张图片', icon: 'none' });
      return;
    }

    this.setData({ isConverting: true });
    wx.showLoading({ title: '正在拼接连续动图...' });

    // wx.uploadFile 每次只能发送一个本地文件：先并发暂存，再一次性合成。
    const stageUploads = this.data.multiImages.map(filePath => new Promise((resolve, reject) => {
      app.uploadFile({
        url: `${app.globalData.baseURL}/api/convert/images-to-gif/frame`,
        filePath: filePath,
        name: 'file',
        success: (res) => {
          try {
            const data = JSON.parse(res.data);
            if (res.statusCode === 200 && data.upload_id) resolve(data.upload_id);
            else reject(new Error(data.detail || '图片上传失败'));
          } catch (err) { reject(err); }
        },
        fail: reject
      });
    }));

    Promise.all(stageUploads).then(uploadIds => {
      app.request({
        url: `${app.globalData.baseURL}/api/convert/images-to-gif/compose`,
        method: 'POST',
        data: { upload_ids: uploadIds, caption: this.data.captionText, fps: 4 },
        success: (res) => {
        wx.hideLoading();
        this.setData({ isConverting: false });
        const data = res.data;
        if (data && data.success) {
          this.setData({ remixResultUrl: `${app.globalData.baseURL}${data.gif_url}` });
          wx.showToast({ title: '合成成功！', icon: 'success' });
        } else {
          wx.showToast({ title: (data && data.detail) || '拼接失败', icon: 'none' });
        }
        },
        fail: () => {
          wx.hideLoading();
          this.setData({ isConverting: false });
          wx.showToast({ title: '合成请求失败', icon: 'none' });
        }
      });
    }).catch((err) => {
      wx.hideLoading();
      this.setData({ isConverting: false });
      wx.showToast({ title: err.message || '图片上传失败', icon: 'none' });
    });
  },

  // 3. 表情包改字
  chooseGifToEdit() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      success: (res) => {
        if (res.tempFiles && res.tempFiles.length > 0) {
          this.setData({ srcGifPath: res.tempFiles[0].tempFilePath });
        }
      }
    });
  },

  clearSrcGif() {
    this.setData({ srcGifPath: '' });
  },

  editGifCaption() {
    if (!this.data.srcGifPath) {
      wx.showToast({ title: '请上传图片或动图', icon: 'none' });
      return;
    }
    if (!this.data.captionText.trim()) {
      wx.showToast({ title: '请输入台词字幕', icon: 'none' });
      return;
    }

    this.setData({ isConverting: true });
    wx.showLoading({ title: '正在合成表情包...' });

    app.uploadFile({
      url: `${app.globalData.baseURL}/api/convert/edit-caption`,
      filePath: this.data.srcGifPath,
      name: 'gif_file',
      formData: {
        caption: this.data.captionText.trim()
      },
      success: (res) => {
        wx.hideLoading();
        this.setData({ isConverting: false });
        let data = res.data;
        try { data = JSON.parse(data); } catch(e) {}
        if (data && data.success) {
          this.setData({ remixResultUrl: `${app.globalData.baseURL}${data.gif_url}` });
          wx.showToast({ title: '合成成功！', icon: 'success' });
        } else {
          wx.showToast({ title: (data && data.detail) || '合成失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        this.setData({ isConverting: false });
        wx.showToast({ title: '网络超时', icon: 'none' });
      }
    });
  },

  // --- 4. 长图智能拼接 ---
  chooseStitchImages() {
    wx.chooseMedia({
      count: 9 - this.data.stitchImages.length,
      mediaType: ['image'],
      success: (res) => {
        if (res.tempFiles && res.tempFiles.length > 0) {
          const newPaths = res.tempFiles.map(f => f.tempFilePath);
          this.setData({
            stitchImages: [...this.data.stitchImages, ...newPaths]
          });
        }
      }
    });
  },

  removeStitchImage(e) {
    if (this.data.isConverting) return;
    const index = Number(e.currentTarget.dataset.index);
    const stitchImages = this.data.stitchImages.filter((_, i) => i !== index);
    this.setData({ stitchImages });
  },

  setStitchMode(e) {
    const mode = e.currentTarget.dataset.mode;
    this.setData({ stitchMode: mode });
  },

  onSubtitleRatioChange(e) {
    this.setData({ subtitleRatio: Number(e.detail.value) });
  },

  executeStitch() {
    if (this.data.stitchImages.length < 2) {
      wx.showToast({ title: '至少需要2张图片进行拼接', icon: 'none' });
      return;
    }

    this.setData({ isConverting: true });
    wx.showLoading({ title: '正在拼接长图...' });

    // 逐张分片暂存后合并
    const stageUploads = this.data.stitchImages.map(filePath => new Promise((resolve, reject) => {
      app.uploadFile({
        url: `${app.globalData.baseURL}/api/convert/images-to-gif/frame`,
        filePath: filePath,
        name: 'file',
        success: (res) => {
          try {
            const data = JSON.parse(res.data);
            if (res.statusCode === 200 && data.upload_id) resolve(data.upload_id);
            else reject(new Error(data.detail || '图片上传失败'));
          } catch (err) { reject(err); }
        },
        fail: reject
      });
    }));

    Promise.all(stageUploads).then(uploadIds => {
      app.request({
        url: `${app.globalData.baseURL}/api/convert/stitch-images`,
        method: 'POST',
        header: { 'content-type': 'application/x-www-form-urlencoded' },
        data: {
          upload_ids: JSON.stringify(uploadIds),
          mode: this.data.stitchMode,
          subtitle_ratio: this.data.subtitleRatio,
          spacing: 2
        },
        success: (res) => {
          wx.hideLoading();
          this.setData({ isConverting: false });
          const data = res.data;
          if (data && data.success) {
            this.setData({ remixResultUrl: `${app.globalData.baseURL}${data.image_url}` });
            wx.showToast({ title: '长图拼接完成！', icon: 'success' });
          } else {
            wx.showToast({ title: (data && data.detail) || '拼接失败', icon: 'none' });
          }
        },
        fail: () => {
          wx.hideLoading();
          this.setData({ isConverting: false });
          wx.showToast({ title: '网络连接失败', icon: 'none' });
        }
      });
    }).catch((err) => {
      wx.hideLoading();
      this.setData({ isConverting: false });
      wx.showToast({ title: err.message || '图片上传失败', icon: 'none' });
    });
  },

  // --- 5. 动图与图片瘦身 ---
  chooseCompressImage() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      success: (res) => {
        if (res.tempFiles && res.tempFiles.length > 0) {
          const file = res.tempFiles[0];
          const bytes = file.size || 0;
          let sizeStr = '';
          if (bytes > 1024 * 1024) {
            sizeStr = (bytes / (1024 * 1024)).toFixed(2) + ' MB';
          } else if (bytes > 0) {
            sizeStr = (bytes / 1024).toFixed(1) + ' KB';
          }
          this.setData({
            compressSrcPath: file.tempFilePath,
            compressFileSizeStr: sizeStr
          });
        }
      }
    });
  },

  clearCompressImage() {
    this.setData({ compressSrcPath: '', compressFileSizeStr: '' });
  },

  setCompressTargetKb(e) {
    const kb = Number(e.currentTarget.dataset.kb);
    this.setData({ compressTargetKb: kb });
  },

  executeCompress() {
    if (!this.data.compressSrcPath) {
      wx.showToast({ title: '请选择需要压缩的文件', icon: 'none' });
      return;
    }

    this.setData({ isConverting: true });
    wx.showLoading({ title: '正在极速智能瘦身...' });

    app.uploadFile({
      url: `${app.globalData.baseURL}/api/convert/compress-image`,
      filePath: this.data.compressSrcPath,
      name: 'file',
      formData: {
        target_kb: this.data.compressTargetKb || 500
      },
      success: (res) => {
        wx.hideLoading();
        this.setData({ isConverting: false });
        let data = res.data;
        try { data = JSON.parse(data); } catch(e) {}
        if (data && data.success) {
          this.setData({ remixResultUrl: `${app.globalData.baseURL}${data.output_url}` });
          wx.showToast({ title: `瘦身成功！(${data.file_size_kb}KB)`, icon: 'success' });
        } else {
          wx.showToast({ title: (data && data.detail) || '压缩失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        this.setData({ isConverting: false });
        wx.showToast({ title: '网络传输超时', icon: 'none' });
      }
    });
  },

  // --- 6. 金句梗图卡片生成器 ---
  onInputCardText(e) {
    this.setData({ cardText: e.detail.value });
  },

  onInputCardTitle(e) {
    this.setData({ cardTitle: e.detail.value });
  },

  onInputCardAuthor(e) {
    this.setData({ cardAuthor: e.detail.value });
  },

  selectCardTheme(e) {
    const theme = e.currentTarget.dataset.theme;
    this.setData({ cardTheme: theme });
  },

  onCardFontSizeChange(e) {
    this.setData({ cardFontSize: Number(e.detail.value) });
  },

  executeGenerateCard() {
    const text = (this.data.cardText || '').trim();
    if (!text) {
      wx.showToast({ title: '请输入金句正文', icon: 'none' });
      return;
    }

    this.setData({ isConverting: true });
    wx.showLoading({ title: '正在排版精美卡片...' });

    app.request({
      url: `${app.globalData.baseURL}/api/convert/text-to-image`,
      method: 'POST',
      header: { 'content-type': 'application/x-www-form-urlencoded' },
      data: {
        text: text,
        theme: this.data.cardTheme || 'classic',
        title: (this.data.cardTitle || '').trim(),
        author: (this.data.cardAuthor || '').trim(),
        font_size: this.data.cardFontSize || 32
      },
      success: (res) => {
        wx.hideLoading();
        this.setData({ isConverting: false });
        const data = res.data;
        if (data && data.success) {
          this.setData({ remixResultUrl: `${app.globalData.baseURL}${data.image_url}` });
          wx.showToast({ title: '卡片生成成功！', icon: 'success' });
        } else {
          wx.showToast({ title: (data && data.detail) || '生成失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        this.setData({ isConverting: false });
        wx.showToast({ title: '网络连接超时', icon: 'none' });
      }
    });
  },

  previewRemixResult(e) {
    const url = e.currentTarget.dataset.url || this.data.remixResultUrl;
    if (!url) return;
    wx.previewImage({ urls: [url], current: url });
  },

  saveRemixGif() {
    if (!this.data.remixResultUrl) return;
    wx.showLoading({ title: '正在下载...' });
    wx.downloadFile({
      url: this.data.remixResultUrl,
      success: (res) => {
        wx.hideLoading();
        if (res.tempFilePath) {
          wx.saveImageToPhotosAlbum({
            filePath: res.tempFilePath,
            success: () => wx.showToast({ title: '已保存至相册', icon: 'success' }),
            fail: () => wx.showToast({ title: '保存失败', icon: 'none' })
          });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '下载失败', icon: 'none' });
      }
    });
  },

  addToCollection() {
    if (!this.data.remixResultUrl) return;
    const openid = app.globalData.openid || wx.getStorageSync('openid');
    wx.showLoading({ title: '正在存入...' });
    app.request({
      url: `${app.globalData.baseURL}/api/collection/list?openid=${openid}`,
      method: 'GET',
      success: (res) => {
        let cols = (res.data && res.data.data) || [];
        const saveToCol = (colId) => {
          app.request({
            url: `${app.globalData.baseURL}/api/collection/add-item`,
            method: 'POST',
            data: {
              collection_id: colId,
              gif_url: this.data.remixResultUrl,
              title: this.data.captionText || '二创表情'
            },
            success: (sRes) => {
              wx.hideLoading();
              wx.showModal({
                title: '存入成功 🎉',
                content: '已成功存入表情合集！可前往底栏【表情合集】查看或打包分享给好友。',
                confirmText: '前往查看',
                cancelText: '留在本页',
                success: (mRes) => {
                  if (mRes.confirm) {
                    wx.switchTab({ url: '/pages/collection/collection' });
                  }
                }
              });
            },
            fail: () => {
              wx.hideLoading();
              wx.showToast({ title: '存入失败', icon: 'none' });
            }
          });
        };

        if (cols.length === 0) {
          app.request({
            url: `${app.globalData.baseURL}/api/collection/create`,
            method: 'POST',
            data: { openid: openid, title: '我的精选表情', description: '默认表情合集' },
            success: (cRes) => {
              if (cRes.data && cRes.data.data) {
                saveToCol(cRes.data.data.collection_id);
              } else {
                wx.hideLoading();
                wx.showToast({ title: '初始化合集失败', icon: 'none' });
              }
            },
            fail: () => {
              wx.hideLoading();
              wx.showToast({ title: '网络连接异常', icon: 'none' });
            }
          });
        } else {
          saveToCol(cols[0].collection_id);
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '网络异常', icon: 'none' });
      }
    });
  },

  onShareAppMessage(options) {
    const user = (app.globalData && app.globalData.userInfo) || {};
    const inviteCode = user.invite_code || app.globalData.inviterCode || '';

    if (this.data.remixResultUrl) {
      const cap = this.data.captionText || '神配文';
      return {
        title: `🔥 看看我给表情包配的文案【${cap}】，太真实了！`,
        path: `/pages/remix/remix?inviter=${inviteCode}`,
        imageUrl: this.data.remixResultUrl
      };
    }

    return {
      title: '表情包自由！一键神配文二次创作你的专属动图',
      path: `/pages/remix/remix?inviter=${inviteCode}`
    };
  },

  onShareTimeline() {
    const cap = this.data.captionText || '神配文';
    return {
      title: `我二创了【${cap}】表情包，快来试试！`,
      imageUrl: this.data.remixResultUrl || ''
    };
  }
});
