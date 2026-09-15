const app = getApp();

const TOOL_META = {
  video: { id: 'video', name: '视频转GIF', icon: '📹' },
  caption: { id: 'caption', name: '加字水印', icon: '💧' },
  compress: { id: 'compress', name: '图片瘦身', icon: '⚡' },
  matting: { id: 'matting', name: '智能抠图', icon: '✂️' },
  picker: { id: 'picker', name: '图片取色', icon: '🔍' },
  images: { id: 'images', name: '多图合成', icon: '▦' },
  stitch: { id: 'stitch', name: '长图拼接', icon: '🎞️' },
  card: { id: 'card', name: '金句卡片', icon: '📜' }
};

Page({
  data: {
    tab: 'video', // 'video' | 'caption' | 'compress' | 'matting' | 'picker' | 'images' | 'stitch' | 'card'
    recentTools: [],

    // 1. 视频转动图
    videoPath: '',
    videoFileSizeStr: '',
    videoStartTime: 0.0,
    videoDuration: 3.0,
    uploadPercent: 0,

    // 通用字幕 / 水印参数 (视频和动图公用)
    captionText: '',
    captionPos: 'bottom', // 'bottom' | 'top' | 'center' | 'top-left' | 'bottom-right' | 'banner-bottom'
    captionFontSize: 24, // 18, 24, 30, 38
    captionOpacity: 1.0, // 1.0, 0.8, 0.6, 0.4
    captionColor: '#ffffff', // '#ffffff', '#facc15', '#ef4444', '#0f172a'

    // 2. 动图/图片加字水印 (原表情包改字升级)
    srcGifPath: '',
    suggestions: [],

    // 3. 多图连续合成动图
    multiImages: [],

    // 4. 长图拼接
    stitchImages: [],
    stitchMode: 'vertical', // 'vertical' | 'horizontal' | 'subtitle'
    subtitleRatio: 0.25,

    // 5. 图片与动图瘦身压缩
    compressSrcPath: '',
    compressFileSizeStr: '',
    compressQuality: 75, // 10% ~ 95%
    compressTargetKb: 500,
    compressOrigSizeKb: 0,
    compressNewSizeKb: 0,
    compressRatioStr: '',

    // 6. 智能抠图换背景
    mattingSrcPath: '',
    mattingBgMode: 'transparent', // 'transparent' | 'white' | 'red' | 'blue' | 'green'
    mattingResultUrl: '',

    // 7. 图片取色器 (RGB & HEX)
    pickerSrcPath: '',
    pickedHex: '#4F46E5',
    pickedRgb: 'rgb(79, 70, 229)',
    pickedX: 0,
    pickedY: 0,
    showPickerLens: false,

    // 8. 金句卡片生成器
    cardText: '',
    cardTheme: 'classic', // 'classic' | 'dark' | 'gold' | 'cute' | 'minimal'
    cardTitle: '',
    cardAuthor: '',
    cardFontSize: 32,

    // 全局合成状态与结果
    isConverting: false,
    remixResultUrl: ''
  },

  onLoad(options) {
    // 1. 初始化最近使用工具
    let recents = wx.getStorageSync('remix_recent_tools');
    if (!recents || !Array.isArray(recents) || recents.length === 0) {
      recents = ['video', 'caption', 'compress', 'matting', 'picker'];
      wx.setStorageSync('remix_recent_tools', recents);
    }
    const recentTools = recents.map(id => TOOL_META[id]).filter(Boolean);
    this.setData({ recentTools });

    if (options && options.tab && TOOL_META[options.tab]) {
      this.setData({ tab: options.tab });
      this.recordRecentTool(options.tab);
    } else {
      this.recordRecentTool(this.data.tab);
    }
  },

  recordRecentTool(tab) {
    let recents = wx.getStorageSync('remix_recent_tools') || ['video', 'caption', 'compress', 'matting'];
    recents = [tab, ...recents.filter(t => t !== tab)].slice(0, 5);
    wx.setStorageSync('remix_recent_tools', recents);
    const recentTools = recents.map(id => TOOL_META[id]).filter(Boolean);
    this.setData({ recentTools });
  },

  switchTab(e) {
    const tab = e.currentTarget.dataset.tab;
    if (!tab) return;
    this.setData({
      tab,
      remixResultUrl: '',
      captionText: ''
    });
    this.recordRecentTool(tab);
  },

  onInputCaption(e) {
    this.setData({ captionText: e.detail.value });
  },

  setCaptionPos(e) {
    const pos = e.currentTarget.dataset.pos;
    this.setData({ captionPos: pos });
  },

  setCaptionFontSize(e) {
    const sz = Number(e.currentTarget.dataset.size);
    this.setData({ captionFontSize: sz });
  },

  setCaptionOpacity(e) {
    const op = Number(e.currentTarget.dataset.op);
    this.setData({ captionOpacity: op });
  },

  setCaptionColor(e) {
    const color = e.currentTarget.dataset.color;
    this.setData({ captionColor: color });
  },

  // ================= 1. 视频转动图 =================
  chooseVideo() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['video'],
      sourceType: ['album', 'camera'],
      maxDuration: 60,
      success: (res) => {
        if (res.tempFiles && res.tempFiles.length > 0) {
          const file = res.tempFiles[0];
          const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
          this.setData({
            videoPath: file.tempFilePath,
            videoFileSizeStr: `${sizeMb} MB`,
            videoStartTime: 0.0,
            videoDuration: Math.min(5.0, Math.max(2.0, (file.duration || 3.0) > 10 ? 3.0 : file.duration)),
            uploadPercent: 0,
            remixResultUrl: ''
          });
        }
      }
    });
  },

  clearVideo() {
    this.setData({ videoPath: '', videoFileSizeStr: '', uploadPercent: 0 });
  },

  onVideoStartTimeChange(e) {
    this.setData({ videoStartTime: Number(e.detail.value) });
  },

  onVideoDurationChange(e) {
    this.setData({ videoDuration: Number(e.detail.value) });
  },

  convertVideoToGif() {
    if (!this.data.videoPath) {
      wx.showToast({ title: '请先选择视频', icon: 'none' });
      return;
    }

    this.setData({ isConverting: true, uploadPercent: 0 });
    wx.showLoading({ title: '上传视频 0%...' });

    const uploadTask = app.uploadFile({
      url: `${app.globalData.baseURL}/api/convert/video-to-gif`,
      filePath: this.data.videoPath,
      name: 'video',
      formData: {
        caption: this.data.captionText.trim(),
        caption_pos: this.data.captionPos || 'bottom',
        font_size: this.data.captionFontSize || 24,
        opacity: this.data.captionOpacity || 1.0,
        color: this.data.captionColor || '#ffffff',
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
      fail: (err) => {
        wx.hideLoading();
        this.setData({ isConverting: false });
        console.error('视频上传失败:', err);
        wx.showToast({ title: '网络超时或视频过大，请重试', icon: 'none' });
      }
    });

    if (uploadTask && uploadTask.onProgressUpdate) {
      uploadTask.onProgressUpdate((res) => {
        this.setData({ uploadPercent: res.progress });
        if (res.progress < 100) {
          wx.showLoading({ title: `上传视频 ${res.progress}%...` });
        } else {
          wx.showLoading({ title: 'FFmpeg 提取精彩动图中...' });
        }
      });
    }
  },

  // ================= 2. 动图/图片加字水印 (表情改字升级) =================
  chooseGifToEdit() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      success: (res) => {
        if (res.tempFiles && res.tempFiles.length > 0) {
          this.setData({ srcGifPath: res.tempFiles[0].tempFilePath, remixResultUrl: '' });
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
      wx.showToast({ title: '请输入水印文字', icon: 'none' });
      return;
    }

    this.setData({ isConverting: true });
    wx.showLoading({ title: '正在合成水印/字幕...' });

    app.uploadFile({
      url: `${app.globalData.baseURL}/api/convert/edit-caption`,
      filePath: this.data.srcGifPath,
      name: 'gif_file',
      formData: {
        caption: this.data.captionText.trim(),
        caption_pos: this.data.captionPos || 'bottom',
        font_size: this.data.captionFontSize || 24,
        opacity: this.data.captionOpacity || 1.0,
        color: this.data.captionColor || '#ffffff'
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
          wx.showToast({ title: '水印加字合成成功！', icon: 'success' });
        } else {
          wx.showToast({ title: (data && data.detail) || '合成失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        this.setData({ isConverting: false });
        wx.showToast({ title: '网络请求失败', icon: 'none' });
      }
    });
  },

  fetchCaptionSuggestions() {
    const kw = (this.data.captionText || '').trim() || '打工';
    wx.showLoading({ title: '寻找爆笑文案...' });
    app.request({
      url: `${app.globalData.baseURL}/api/convert/caption-suggest`,
      method: 'POST',
      header: { 'content-type': 'application/x-www-form-urlencoded' },
      data: { keyword: kw },
      success: (res) => {
        wx.hideLoading();
        if (res.data && res.data.suggestions) {
          this.setData({ suggestions: res.data.suggestions });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '推荐文案获取失败', icon: 'none' });
      }
    });
  },

  applySuggestion(e) {
    const text = e.currentTarget.dataset.text;
    this.setData({ captionText: text });
  },

  // ================= 3. 图片瘦身压缩 =================
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
            compressFileSizeStr: sizeStr,
            compressOrigSizeKb: Math.round(bytes / 1024),
            compressNewSizeKb: 0,
            compressRatioStr: '',
            remixResultUrl: ''
          });
        }
      }
    });
  },

  clearCompressImage() {
    this.setData({
      compressSrcPath: '',
      compressFileSizeStr: '',
      compressOrigSizeKb: 0,
      compressNewSizeKb: 0,
      compressRatioStr: ''
    });
  },

  onCompressQualityChange(e) {
    this.setData({ compressQuality: Number(e.detail.value) });
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
    wx.showLoading({ title: '正在智能压缩瘦身...' });

    app.uploadFile({
      url: `${app.globalData.baseURL}/api/convert/compress-image`,
      filePath: this.data.compressSrcPath,
      name: 'file',
      formData: {
        target_kb: this.data.compressTargetKb || 500,
        quality: this.data.compressQuality || 75
      },
      success: (res) => {
        wx.hideLoading();
        this.setData({ isConverting: false });
        let data = res.data;
        if (typeof data === 'string') {
          try { data = JSON.parse(data); } catch(e) {}
        }
        if (data && data.success) {
          const origKb = data.original_size_kb || this.data.compressOrigSizeKb;
          const newKb = data.file_size_kb || 0;
          let ratioStr = '';
          if (origKb > 0 && newKb < origKb) {
            const pct = Math.round((1 - newKb / origKb) * 100);
            ratioStr = `-${pct}%`;
          }
          this.setData({
            remixResultUrl: `${app.globalData.baseURL}${data.output_url}`,
            compressOrigSizeKb: origKb,
            compressNewSizeKb: newKb,
            compressRatioStr: ratioStr
          });
          wx.showToast({ title: `瘦身成功！(${newKb}KB)`, icon: 'success' });
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

  // ================= 4. 智能抠图换背景 =================
  chooseMattingImage() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      success: (res) => {
        if (res.tempFiles && res.tempFiles.length > 0) {
          this.setData({
            mattingSrcPath: res.tempFiles[0].tempFilePath,
            mattingResultUrl: '',
            remixResultUrl: ''
          });
          // 自动开始抠图
          this.executeMatting();
        }
      }
    });
  },

  clearMattingImage() {
    this.setData({ mattingSrcPath: '', mattingResultUrl: '' });
  },

  setMattingBg(e) {
    const bg = e.currentTarget.dataset.bg;
    this.setData({ mattingBgMode: bg });
    if (this.data.mattingSrcPath) {
      this.executeMatting();
    }
  },

  executeMatting() {
    if (!this.data.mattingSrcPath) {
      wx.showToast({ title: '请先选择图片', icon: 'none' });
      return;
    }

    this.setData({ isConverting: true });
    wx.showLoading({ title: 'AI 智能分离主体中...' });

    app.uploadFile({
      url: `${app.globalData.baseURL}/api/convert/matting`,
      filePath: this.data.mattingSrcPath,
      name: 'file',
      formData: {
        bg_mode: this.data.mattingBgMode || 'transparent'
      },
      success: (res) => {
        wx.hideLoading();
        this.setData({ isConverting: false });
        let data = res.data;
        if (typeof data === 'string') {
          try { data = JSON.parse(data); } catch(e) {}
        }
        if (data && data.success) {
          const fullUrl = `${app.globalData.baseURL}${data.output_url}`;
          this.setData({
            mattingResultUrl: fullUrl,
            remixResultUrl: fullUrl
          });
          wx.showToast({ title: '抠图换底成功！', icon: 'success' });
        } else {
          wx.showToast({ title: (data && data.detail) || '抠图失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        this.setData({ isConverting: false });
        wx.showToast({ title: '抠图请求失败', icon: 'none' });
      }
    });
  },

  // ================= 5. 图片取色器 (RGB & HEX) =================
  choosePickerImage() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      success: (res) => {
        if (res.tempFiles && res.tempFiles.length > 0) {
          const src = res.tempFiles[0].tempFilePath;
          this.setData({ pickerSrcPath: src, showPickerLens: false });
          setTimeout(() => {
            this.initPickerCanvas(src);
          }, 150);
        }
      }
    });
  },

  clearPickerImage() {
    this.setData({ pickerSrcPath: '', showPickerLens: false });
  },

  initPickerCanvas(src) {
    const query = wx.createSelectorQuery();
    query.select('#pickerCanvas')
      .fields({ node: true, size: true })
      .exec((res) => {
        if (!res[0] || !res[0].node) return;
        const canvas = res[0].node;
        const ctx = canvas.getContext('2d');
        const windowInfo = (wx.getWindowInfo && wx.getWindowInfo()) || (wx.getSystemInfoSync ? wx.getSystemInfoSync() : {});
        const dpr = windowInfo.pixelRatio || 2;
        const w = res[0].width;
        const h = res[0].height;
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        ctx.scale(dpr, dpr);

        this.pickerCanvas = canvas;
        this.pickerCtx = ctx;
        this.pickerDpr = dpr;
        this.pickerW = w;
        this.pickerH = h;

        const img = canvas.createImage();
        img.onload = () => {
          this.pickerImgObj = img;
          ctx.clearRect(0, 0, w, h);
          const r = Math.min(w / img.width, h / img.height);
          const dw = img.width * r;
          const dh = img.height * r;
          const dx = (w - dw) / 2;
          const dy = (h - dh) / 2;
          this.pickerDrawInfo = { dx, dy, dw, dh };
          ctx.drawImage(img, dx, dy, dw, dh);

          // 自动吸取中心像素
          this.samplePixelAt(Math.round(w / 2), Math.round(h / 2));
        };
        img.src = src;
      });
  },

  onPickerCanvasTouch(e) {
    if (!this.pickerCtx || !this.pickerCanvas) return;
    const touch = e.touches[0];
    const query = wx.createSelectorQuery();
    query.select('#pickerCanvas').boundingClientRect((rect) => {
      if (!rect) return;
      const x = Math.max(0, Math.min(touch.clientX - rect.left, this.pickerW - 1));
      const y = Math.max(0, Math.min(touch.clientY - rect.top, this.pickerH - 1));
      this.samplePixelAt(x, y);
    }).exec();
  },

  samplePixelAt(x, y) {
    try {
      const dpr = this.pickerDpr || 2;
      const imgData = this.pickerCtx.getImageData(Math.floor(x * dpr), Math.floor(y * dpr), 1, 1);
      const [r, g, b, a] = imgData.data;
      const toHex = (n) => n.toString(16).padStart(2, '0').toUpperCase();
      const hex = `#${toHex(r)}${toHex(g)}${toHex(b)}`;
      const rgb = `rgb(${r}, ${g}, ${b})`;
      this.setData({
        pickedHex: hex,
        pickedRgb: rgb,
        pickedX: Math.round(x),
        pickedY: Math.round(y),
        showPickerLens: true
      });
    } catch (e) {
      console.warn('取色失败:', e);
    }
  },

  copyHex() {
    wx.setClipboardData({
      data: this.data.pickedHex,
      success: () => {
        wx.showToast({ title: `HEX ${this.data.pickedHex} 已复制`, icon: 'success' });
      }
    });
  },

  copyRgb() {
    wx.setClipboardData({
      data: this.data.pickedRgb,
      success: () => {
        wx.showToast({ title: `RGB 已复制`, icon: 'success' });
      }
    });
  },

  // ================= 6. 多图合成动图 =================
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

  // ================= 7. 长图智能拼接 =================
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

  // ================= 8. 金句梗图卡片 =================
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

  // ================= 结果预览、保存与分享 =================
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
              title: this.data.captionText || '百宝箱创作'
            },
            success: () => {
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

  onShareAppMessage() {
    const user = (app.globalData && app.globalData.userInfo) || {};
    const inviteCode = user.invite_code || app.globalData.inviterCode || '';

    if (this.data.remixResultUrl) {
      const cap = this.data.captionText || '精彩作品';
      return {
        title: `🔥 看看我用图片百宝箱制作的【${cap}】，太棒了！`,
        path: `/pages/remix/remix?inviter=${inviteCode}`,
        imageUrl: this.data.remixResultUrl
      };
    }

    return {
      title: '图片百宝箱：视频转GIF、智能抠图、取色器、压缩瘦身！',
      path: `/pages/remix/remix?inviter=${inviteCode}`
    };
  },

  onShareTimeline() {
    const cap = this.data.captionText || '精彩作品';
    return {
      title: `我在图片百宝箱制作了【${cap}】，快来体验！`,
      imageUrl: this.data.remixResultUrl || ''
    };
  }
});
