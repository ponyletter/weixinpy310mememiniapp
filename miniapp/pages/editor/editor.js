const app = getApp();

Page({
  data: {
    bgImageSrc: '',
    canvasWidth: 350,
    canvasHeight: 350,
    activeTab: 'sticker', // 'sticker' | 'text' | 'shape' | 'brush'
    stickerCategory: 'emoji', // 'emoji' | 'badge'
    selectedElementId: null,

    // 贴纸库数据
    emojiList: [
      '🤣', '😎', '😭', '🥺', '😡', '🐼', '🐮', '🐱', '🐶', '🐷',
      '💩', '🔥', '💯', '💖', '💔', '💣', '🍺', '💤', '💢', '💨',
      '🕶️', '👑', '🎩', '🎀', '🎁', '🚀', '💰', '💥', '👻', '🤡'
    ],
    badgeList: [
      '暴富', '绝了', '稳了', '收到', '摸鱼', '下班',
      '躺平', '冲鸭', '破防', '无语', '太难了', '问号???',
      '蚌埠住了', '芜湖起飞', '尊嘟假嘟', '奥利给', '安排'
    ],

    // 文字输入弹窗状态
    showTextModal: false,
    textInputVal: '',
    textColor: '#1e293b',
    textBgColor: '#000000',
    textSize: 28,
    textHasOutline: true,
    availableColors: ['#1e293b', '#ffffff', '#ef4444', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6', '#ec4899'],

    // 涂鸦画笔状态
    isBrushActive: false,
    brushColor: '#1e293b',
    brushWidth: 4,

    // 底图适配、变换与裁剪控制 (Apple 风格)
    cropSubTab: 'crop', // 'crop' | 'adjust' | 'filter'
    bgFitMode: 'cover', // 'contain' | 'cover'
    bgScale: 1.0,
    bgOffsetX: 0,
    bgOffsetY: 0,
    bgRotation: 0,
    bgFlipH: false,

    // 调色参数 (曝光/对比度/饱和度/亮度)
    imgExposure: 0,   // -100 ~ +100
    imgContrast: 0,   // -50 ~ +50
    imgSaturation: 0, // -50 ~ +50
    imgBrightness: 0, // -50 ~ +50

    // 滤镜风格
    imgFilter: 'original', // 'original' | 'vivid' | 'warm' | 'cool' | 'mono' | 'film'

    // 交互式裁剪框与快照
    cropRatio: 'free', // 'free' | '1:1' | '4:3' | '3:4' | '16:9'
    cropBox: { x: 12, y: 12, w: 260, h: 260 },
    modalCanvasSnapshot: '',

    // 元素属性控制条 (当前选中元素)
    selectedScale: 1.0,
    selectedRotate: 0
  },

  onLoad(options) {
    const src = options.src ? decodeURIComponent(options.src) : '';
    const isCrop = options && options.mode === 'crop';
    this.elements = []; // 画布上的所有图元
    this.brushStrokes = []; // 涂鸦线条
    this.brushRedoStack = []; // 涂鸦前进/恢复历史
    this.elementRedoStack = []; // 图元前进/恢复历史
    this.undoStack = []; // 撤销历史
    this.bgImageObj = null;
    this.elementCounter = 1;

    // 获取设备屏幕宽度以适配画布 (采用新 API 避免废弃警告)
    const windowInfo = (wx.getWindowInfo && wx.getWindowInfo()) || (wx.getSystemInfoSync ? wx.getSystemInfoSync() : {});
    const winWidth = windowInfo.windowWidth || 375;
    const cWidth = Math.min(winWidth - 32, 380);
    const cHeight = cWidth; // 1:1 正方形画布，最适合表情包
    const pad = 12;
    this.setData({
      bgImageSrc: src,
      canvasWidth: cWidth,
      canvasHeight: cHeight,
      cropBox: { x: pad, y: pad, w: cWidth - pad * 2, h: cHeight - pad * 2 },
      cropRatio: 'free',
      activeTab: isCrop ? 'crop' : 'sticker',
      cropSubTab: 'crop',
      bgFitMode: isCrop ? 'cover' : 'contain'
    });

    setTimeout(() => {
      this.initCanvas(src);
    }, 200);
  },

  initCanvas(bgSrc) {
    const query = wx.createSelectorQuery();
    query.select('#editorCanvas')
      .fields({ node: true, size: true })
      .exec((res) => {
        if (!res[0] || !res[0].node) return;
        const canvas = res[0].node;
        const ctx = canvas.getContext('2d');
        const windowInfo = (wx.getWindowInfo && wx.getWindowInfo()) || (wx.getSystemInfoSync ? wx.getSystemInfoSync() : {});
        const dpr = windowInfo.pixelRatio || 2;

        canvas.width = res[0].width * dpr;
        canvas.height = res[0].height * dpr;
        ctx.scale(dpr, dpr);

        this.canvas = canvas;
        this.ctx = ctx;
        this.dpr = dpr;

        if (bgSrc) {
          wx.showLoading({ title: '加载底图中...' });
          const img = canvas.createImage();
          img.onload = () => {
            wx.hideLoading();
            this.bgImageObj = img;
            this.renderCanvas();
          };
          img.onerror = () => {
            wx.hideLoading();
            this.renderCanvas();
          };
          img.src = bgSrc;
        } else {
          this.renderCanvas();
        }
      });
  },

  // --- 画布全局重绘引擎 ---
  renderCanvas() {
    if (!this.ctx || !this.canvas) return;
    const ctx = this.ctx;
    const w = this.data.canvasWidth;
    const h = this.data.canvasHeight;

    // 1. 清屏并绘制白底
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, w, h);

    // 2. 绘制底图 (居中 Cover / Contain 适配、缩放、平移、旋转与 Apple 风格调色滤镜)
    if (this.bgImageObj) {
      const img = this.bgImageObj;
      const imgW = img.width || w;
      const imgH = img.height || h;
      const fitRatio = this.data.bgFitMode === 'cover' ? Math.max(w / imgW, h / imgH) : Math.min(w / imgW, h / imgH);
      const scale = fitRatio * (this.data.bgScale || 1.0);
      const drawW = imgW * scale;
      const drawH = imgH * scale;

      // 计算滤镜属性 (曝光、亮度、对比度、饱和度与 Apple 风格滤镜)
      const expFactor = 1 + (this.data.imgExposure || 0) / 100;
      const brightFactor = 1 + (this.data.imgBrightness || 0) / 100;
      const totalBright = Math.max(0, Math.round(expFactor * brightFactor * 100));
      const contrastFactor = Math.max(0, Math.round((1 + (this.data.imgContrast || 0) / 100) * 100));
      let satFactor = Math.max(0, Math.round((1 + (this.data.imgSaturation || 0) / 100) * 100));

      let sepia = 0;
      let hueRotate = 0;
      let grayscale = 0;

      switch (this.data.imgFilter) {
        case 'vivid':
          satFactor = Math.round(satFactor * 1.35);
          break;
        case 'warm':
          sepia = 30;
          break;
        case 'cool':
          hueRotate = 180;
          break;
        case 'mono':
          grayscale = 100;
          break;
        case 'film':
          sepia = 35;
          satFactor = Math.round(satFactor * 0.85);
          break;
        case 'original':
        default:
          break;
      }

      const filters = [];
      if (totalBright !== 100) filters.push(`brightness(${totalBright}%)`);
      if (contrastFactor !== 100) filters.push(`contrast(${contrastFactor}%)`);
      if (satFactor !== 100) filters.push(`saturate(${satFactor}%)`);
      if (grayscale > 0) filters.push(`grayscale(${grayscale}%)`);
      if (sepia > 0) filters.push(`sepia(${sepia}%)`);
      if (hueRotate > 0) filters.push(`hue-rotate(${hueRotate}deg)`);

      ctx.save();
      if (filters.length > 0 && typeof ctx.filter !== 'undefined') {
        try {
          ctx.filter = filters.join(' ');
        } catch (e) {}
      }

      const cx = w / 2 + (this.data.bgOffsetX || 0);
      const cy = h / 2 + (this.data.bgOffsetY || 0);
      ctx.translate(cx, cy);

      if (this.data.bgRotation) {
        ctx.rotate((this.data.bgRotation * Math.PI) / 180);
      }
      if (this.data.bgFlipH) {
        ctx.scale(-1, 1);
      }

      ctx.drawImage(img, -drawW / 2, -drawH / 2, drawW, drawH);
      ctx.restore();
      if (typeof ctx.filter !== 'undefined') {
        try { ctx.filter = 'none'; } catch (e) {}
      }
    }

    // 3. 绘制涂鸦画笔线条
    for (const stroke of this.brushStrokes) {
      if (stroke.points.length < 2) continue;
      ctx.save();
      ctx.strokeStyle = stroke.color;
      ctx.lineWidth = stroke.width;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.beginPath();
      ctx.moveTo(stroke.points[0].x, stroke.points[0].y);
      for (let i = 1; i < stroke.points.length; i++) {
        ctx.lineTo(stroke.points[i].x, stroke.points[i].y);
      }
      ctx.stroke();
      ctx.restore();
    }

    // 4. 绘制所有图元元素 (贴纸、徽章、文本、形状)
    for (const el of this.elements) {
      this.drawElement(ctx, el, el.id === this.data.selectedElementId);
    }
  },

  // --- 绘制单个图元 ---
  drawElement(ctx, el, isSelected) {
    ctx.save();
    ctx.translate(el.x, el.y);
    ctx.rotate((el.rotation * Math.PI) / 180);
    ctx.scale(el.scale, el.scale);

    let boxW = 60;
    let boxH = 60;

    if (el.type === 'sticker') {
      // 绘制 Emoji 贴纸
      const fontSize = el.fontSize || 48;
      ctx.font = `${fontSize}px sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(el.content, 0, 0);
      boxW = fontSize * 1.2;
      boxH = fontSize * 1.2;
    } else if (el.type === 'badge') {
      // 绘制梗图勋章贴纸
      const fontSize = el.fontSize || 22;
      ctx.font = `bold ${fontSize}px sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      const textMetrics = ctx.measureText(el.content);
      const textW = textMetrics.width;
      boxW = textW + 28;
      boxH = fontSize + 20;

      // 贴纸圆角矩形背景 (经典红/黄底白字带描边)
      ctx.fillStyle = el.bgColor || '#ef4444';
      ctx.beginPath();
      ctx.roundRect(-boxW / 2, -boxH / 2, boxW, boxH, 12);
      ctx.fill();

      // 白色粗边框
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 3;
      ctx.stroke();

      // 文字
      ctx.fillStyle = el.color || '#ffffff';
      ctx.fillText(el.content, 0, 1);
    } else if (el.type === 'text') {
      // 绘制自定义表情包文字
      const fontSize = el.fontSize || 28;
      ctx.font = `bold ${fontSize}px sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      const textMetrics = ctx.measureText(el.content);
      const textW = textMetrics.width;
      boxW = textW + 20;
      boxH = fontSize + 16;

      if (el.hasOutline) {
        // 智能根据文字深浅选用描边颜色，避免深底或浅底时字迹无法辨识
        const isDark = (el.color === '#1e293b' || el.color === '#000000');
        ctx.strokeStyle = isDark ? '#ffffff' : '#000000';
        ctx.lineWidth = 4;
        ctx.lineJoin = 'round';
        ctx.strokeText(el.content, 0, 0);
      }

      ctx.fillStyle = el.color || '#ffffff';
      ctx.fillText(el.content, 0, 0);
    } else if (el.type === 'shape') {
      // 绘制几何形状与气泡
      boxW = el.width || 80;
      boxH = el.height || 60;
      ctx.fillStyle = el.bgColor || 'rgba(255, 255, 255, 0.9)';
      ctx.strokeStyle = el.color || '#1e293b';
      ctx.lineWidth = el.strokeWidth || 3;

      if (el.shapeType === 'rect') {
        // 圆角矩形框
        ctx.beginPath();
        ctx.roundRect(-boxW / 2, -boxH / 2, boxW, boxH, 10);
        if (el.fill) ctx.fill();
        ctx.stroke();
      } else if (el.shapeType === 'circle') {
        // 圆形
        ctx.beginPath();
        ctx.arc(0, 0, boxW / 2, 0, Math.PI * 2);
        if (el.fill) ctx.fill();
        ctx.stroke();
      } else if (el.shapeType === 'bubble') {
        // 漫画对话气泡
        ctx.beginPath();
        const rw = boxW;
        const rh = boxH - 14;
        ctx.roundRect(-rw / 2, -rh / 2 - 7, rw, rh, 14);
        // 气泡尾巴尖角
        ctx.moveTo(-10, rh / 2 - 7);
        ctx.lineTo(-24, rh / 2 + 10);
        ctx.lineTo(6, rh / 2 - 7);
        ctx.fill();
        ctx.stroke();

        if (el.content) {
          ctx.font = 'bold 20px sans-serif';
          ctx.fillStyle = el.color || '#1e293b';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(el.content, 0, -7);
        }
      } else if (el.shapeType === 'arrow') {
        // 红色指示箭头
        ctx.beginPath();
        ctx.strokeStyle = el.color || '#ef4444';
        ctx.lineWidth = 5;
        ctx.moveTo(-boxW / 2, boxH / 2);
        ctx.lineTo(boxW / 2, -boxH / 2);
        ctx.stroke();
        // 箭头头部
        ctx.beginPath();
        ctx.fillStyle = el.color || '#ef4444';
        ctx.moveTo(boxW / 2, -boxH / 2);
        ctx.lineTo(boxW / 2 - 18, -boxH / 2 + 4);
        ctx.lineTo(boxW / 2 - 4, -boxH / 2 + 18);
        ctx.closePath();
        ctx.fill();
      }
    }

    // 保存计算出的尺寸供命中检测使用
    el._boxW = boxW;
    el._boxH = boxH;

    // 5. 如果是当前选中元素，绘制虚线选框和删除 handle
    if (isSelected && !this.data.isBrushActive) {
      const pad = 8;
      const selW = boxW + pad * 2;
      const selH = boxH + pad * 2;

      ctx.strokeStyle = '#4f46e5';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.strokeRect(-selW / 2, -selH / 2, selW, selH);
      ctx.setLineDash([]);

      // 右上角删除红点 (✕)
      ctx.fillStyle = '#ef4444';
      ctx.beginPath();
      ctx.arc(selW / 2, -selH / 2, 10, 0, Math.PI * 2);
      ctx.fill();
      ctx.font = 'bold 12px sans-serif';
      ctx.fillStyle = '#ffffff';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('✕', selW / 2, -selH / 2);

      // 右下角缩放蓝点 (⤡)
      ctx.fillStyle = '#4f46e5';
      ctx.beginPath();
      ctx.arc(selW / 2, selH / 2, 10, 0, Math.PI * 2);
      ctx.fill();
      ctx.font = 'bold 11px sans-serif';
      ctx.fillStyle = '#ffffff';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('⤡', selW / 2, selH / 2);
    }

    ctx.restore();
  },

  // --- 触摸事件处理 (拖拽、缩放与涂鸦) ---
  onTouchStart(e) {
    const touch = e.touches[0];
    const x = touch.x;
    const y = touch.y;

    if (this.data.isBrushActive) {
      // 涂鸦模式
      this.currentStroke = {
        color: this.data.brushColor,
        width: this.data.brushWidth,
        points: [{ x, y }]
      };
      this.brushStrokes.push(this.currentStroke);
      this.brushRedoStack = [];
      this.renderCanvas();
      return;
    }

    // 检查是否点中了当前选中元素的右上角删除按钮 (✕)
    const selectedEl = this.elements.find(el => el.id === this.data.selectedElementId);
    if (selectedEl && selectedEl._boxW) {
      const selW = selectedEl._boxW + 16;
      const selH = selectedEl._boxH + 16;
      // 转换坐标至选中元素本地坐标系
      const dx = x - selectedEl.x;
      const dy = y - selectedEl.y;
      const rad = (-selectedEl.rotation * Math.PI) / 180;
      const localX = (dx * Math.cos(rad) - dy * Math.sin(rad)) / selectedEl.scale;
      const localY = (dx * Math.sin(rad) + dy * Math.cos(rad)) / selectedEl.scale;

      const delDist = Math.hypot(localX - selW / 2, localY - (-selH / 2));
      if (delDist < 18) {
        this.deleteSelectedElement();
        return;
      }
    }

    // 命中测试：从最上层元素向下查找
    let hitEl = null;
    for (let i = this.elements.length - 1; i >= 0; i--) {
      const el = this.elements[i];
      const boxW = (el._boxW || 60) * el.scale;
      const boxH = (el._boxH || 60) * el.scale;
      if (Math.abs(x - el.x) <= boxW / 2 + 10 && Math.abs(y - el.y) <= boxH / 2 + 10) {
        hitEl = el;
        break;
      }
    }

    if (hitEl) {
      this.setData({
        selectedElementId: hitEl.id,
        selectedScale: hitEl.scale,
        selectedRotate: hitEl.rotation
      });
      this.isDragging = true;
      this.dragStartX = x;
      this.dragStartY = y;
      this.elStartX = hitEl.x;
      this.elStartY = hitEl.y;
      this.renderCanvas();
    } else {
      // 点击空白处取消选中：若处于裁剪构图模式且有底图，则支持拖拽平移底图
      this.setData({ selectedElementId: null });
      if (this.data.activeTab === 'crop' && this.bgImageObj) {
        this.isBgDragging = true;
        this.bgDragStartX = x;
        this.bgDragStartY = y;
        this.bgDragInitX = this.data.bgOffsetX || 0;
        this.bgDragInitY = this.data.bgOffsetY || 0;
      }
      this.renderCanvas();
    }
  },

  onTouchMove(e) {
    const touch = e.touches[0];
    const x = touch.x;
    const y = touch.y;

    if (this.data.isBrushActive && this.currentStroke) {
      this.currentStroke.points.push({ x, y });
      this.renderCanvas();
      return;
    }

    if (this.isBgDragging) {
      const dx = x - this.bgDragStartX;
      const dy = y - this.bgDragStartY;
      this.setData({
        bgOffsetX: Math.round(this.bgDragInitX + dx),
        bgOffsetY: Math.round(this.bgDragInitY + dy)
      });
      this.renderCanvas();
      return;
    }

    if (this.isDragging && this.data.selectedElementId) {
      const el = this.elements.find(item => item.id === this.data.selectedElementId);
      if (el) {
        el.x = this.elStartX + (x - this.dragStartX);
        el.y = this.elStartY + (y - this.dragStartY);
        this.renderCanvas();
      }
    }
  },

  onTouchEnd() {
    this.isDragging = false;
    this.isBgDragging = false;
    this.currentStroke = null;
  },

  // --- 添加图元逻辑 ---
  addSticker(e) {
    const emoji = e.currentTarget.dataset.emoji;
    const center = this.getCanvasCenter();
    const newEl = {
      id: `sticker_${this.elementCounter++}`,
      type: 'sticker',
      content: emoji,
      x: center.x,
      y: center.y,
      scale: 1.0,
      rotation: 0,
      fontSize: 48
    };
    this.elements.push(newEl);
    this.elementRedoStack = [];
    this.setData({
      selectedElementId: newEl.id,
      selectedScale: 1.0,
      selectedRotate: 0
    });
    this.renderCanvas();
  },

  addBadge(e) {
    const text = e.currentTarget.dataset.text;
    const center = this.getCanvasCenter();
    const colors = ['#ef4444', '#f59e0b', '#3b82f6', '#10b981', '#8b5cf6'];
    const randomBg = colors[Math.floor(Math.random() * colors.length)];
    const newEl = {
      id: `badge_${this.elementCounter++}`,
      type: 'badge',
      content: text,
      x: center.x,
      y: center.y,
      scale: 1.0,
      rotation: (Math.random() - 0.5) * 16, // 微斜角度更具动感
      color: '#ffffff',
      bgColor: randomBg,
      fontSize: 22
    };
    this.elements.push(newEl);
    this.elementRedoStack = [];
    this.setData({
      selectedElementId: newEl.id,
      selectedScale: 1.0,
      selectedRotate: Math.round(newEl.rotation)
    });
    this.renderCanvas();
  },

  addShape(e) {
    const shapeType = e.currentTarget.dataset.shape;
    const center = this.getCanvasCenter();
    let newEl = null;

    if (shapeType === 'bubble') {
      newEl = {
        id: `shape_${this.elementCounter++}`,
        type: 'shape',
        shapeType: 'bubble',
        content: '在这里输入',
        x: center.x,
        y: center.y - 40,
        width: 140,
        height: 64,
        scale: 1.0,
        rotation: 0,
        color: '#1e293b',
        bgColor: '#ffffff'
      };
    } else if (shapeType === 'arrow') {
      newEl = {
        id: `shape_${this.elementCounter++}`,
        type: 'shape',
        shapeType: 'arrow',
        x: center.x,
        y: center.y,
        width: 90,
        height: 60,
        scale: 1.0,
        rotation: 0,
        color: '#ef4444'
      };
    } else if (shapeType === 'rect') {
      newEl = {
        id: `shape_${this.elementCounter++}`,
        type: 'shape',
        shapeType: 'rect',
        x: center.x,
        y: center.y,
        width: 120,
        height: 80,
        scale: 1.0,
        rotation: 0,
        fill: false,
        color: '#ef4444',
        strokeWidth: 3
      };
    } else if (shapeType === 'circle') {
      newEl = {
        id: `shape_${this.elementCounter++}`,
        type: 'shape',
        shapeType: 'circle',
        x: center.x,
        y: center.y,
        width: 90,
        height: 90,
        scale: 1.0,
        rotation: 0,
        fill: false,
        color: '#ef4444',
        strokeWidth: 3
      };
    }

    if (newEl) {
      this.elements.push(newEl);
      this.elementRedoStack = [];
      this.setData({
        selectedElementId: newEl.id,
        selectedScale: 1.0,
        selectedRotate: 0
      });
      this.renderCanvas();
    }
  },

  // --- 文字弹窗与添加 ---
  openTextModal() {
    if (this.canvas) {
      wx.canvasToTempFilePath({
        canvas: this.canvas,
        fileType: 'png',
        quality: 1,
        success: (res) => {
          this.setData({
            modalCanvasSnapshot: res.tempFilePath,
            showTextModal: true,
            textInputVal: ''
          });
        },
        fail: () => {
          this.setData({
            showTextModal: true,
            textInputVal: ''
          });
        }
      });
    } else {
      this.setData({
        showTextModal: true,
        textInputVal: ''
      });
    }
  },

  closeTextModal() {
    this.setData({
      showTextModal: false,
      modalCanvasSnapshot: ''
    });
  },

  onTextInput(e) {
    this.setData({ textInputVal: e.detail.value });
  },

  selectTextColor(e) {
    const color = e.currentTarget.dataset.color;
    this.setData({ textColor: color });
  },

  toggleTextOutline() {
    this.setData({ textHasOutline: !this.data.textHasOutline });
  },

  setTextSize(e) {
    const size = Number(e.currentTarget.dataset.size);
    this.setData({ textSize: size });
  },

  confirmAddText() {
    const text = (this.data.textInputVal || '').trim();
    if (!text) {
      wx.showToast({ title: '请输入文字内容', icon: 'none' });
      return;
    }
    const center = this.getCanvasCenter();
    const newEl = {
      id: `text_${this.elementCounter++}`,
      type: 'text',
      content: text,
      x: center.x,
      y: center.y,
      scale: 1.0,
      rotation: 0,
      color: this.data.textColor,
      fontSize: this.data.textSize,
      hasOutline: this.data.textHasOutline
    };
    this.elements.push(newEl);
    this.elementRedoStack = [];
    this.setData({
      showTextModal: false,
      modalCanvasSnapshot: '',
      selectedElementId: newEl.id,
      selectedScale: 1.0,
      selectedRotate: 0
    });
    this.renderCanvas();
  },

  // --- 选中元素属性调节 ---
  onScaleChange(e) {
    const val = Number(e.detail.value);
    this.setData({ selectedScale: val });
    const el = this.elements.find(item => item.id === this.data.selectedElementId);
    if (el) {
      el.scale = val;
      this.renderCanvas();
    }
  },

  onRotateChange(e) {
    const val = Number(e.detail.value);
    this.setData({ selectedRotate: val });
    const el = this.elements.find(item => item.id === this.data.selectedElementId);
    if (el) {
      el.rotation = val;
      this.renderCanvas();
    }
  },

  deleteSelectedElement() {
    if (!this.data.selectedElementId) return;
    this.elements = this.elements.filter(el => el.id !== this.data.selectedElementId);
    this.setData({ selectedElementId: null });
    this.renderCanvas();
  },

  // --- 涂鸦画笔工具设置 ---
  toggleBrushMode() {
    const next = !this.data.isBrushActive;
    this.setData({
      isBrushActive: next,
      selectedElementId: null
    });
    this.renderCanvas();
    wx.showToast({
      title: next ? '已开启涂鸦模式' : '已退出涂鸦',
      icon: 'none'
    });
  },

  selectBrushColor(e) {
    const color = e.currentTarget.dataset.color;
    this.setData({ brushColor: color });
  },

  selectBrushWidth(e) {
    const w = Number(e.currentTarget.dataset.w);
    this.setData({ brushWidth: w });
  },

  clearBrush() {
    this.brushStrokes = [];
    this.brushRedoStack = [];
    this.renderCanvas();
    wx.showToast({ title: '涂鸦已清空', icon: 'none' });
  },

  // --- 底部 Tab 切换 ---
  switchTab(e) {
    const tab = e.currentTarget.dataset.tab;
    const isBrush = tab === 'brush';
    this.setData({
      activeTab: tab,
      isBrushActive: isBrush,
      selectedElementId: isBrush ? null : this.data.selectedElementId
    });
    this.renderCanvas();
    if (isBrush) {
      wx.showToast({ title: '已开启涂鸦模式', icon: 'none' });
    }
  },

  stopBubble() {
    // 阻止模态框内点击向外冒泡关闭弹窗
  },

  switchStickerCategory(e) {
    const cat = e.currentTarget.dataset.cat;
    this.setData({ stickerCategory: cat });
  },

  // --- 画布全局操作 (撤销与前进/恢复) ---
  undo() {
    if (this.data.isBrushActive) {
      if (this.brushStrokes.length > 0) {
        const stroke = this.brushStrokes.pop();
        this.brushRedoStack.push(stroke);
        this.renderCanvas();
        wx.showToast({ title: '已撤销笔画', icon: 'none', duration: 800 });
      } else {
        wx.showToast({ title: '无可撤销笔画', icon: 'none' });
      }
      return;
    }
    if (this.elements.length > 0) {
      const el = this.elements.pop();
      this.elementRedoStack.push(el);
      this.setData({ selectedElementId: null });
      this.renderCanvas();
      wx.showToast({ title: '已撤销元素', icon: 'none', duration: 800 });
    } else if (this.brushStrokes.length > 0) {
      const stroke = this.brushStrokes.pop();
      this.brushRedoStack.push(stroke);
      this.renderCanvas();
      wx.showToast({ title: '已撤销笔画', icon: 'none', duration: 800 });
    } else {
      wx.showToast({ title: '无可撤销内容', icon: 'none' });
    }
  },

  redo() {
    if (this.data.isBrushActive) {
      if (this.brushRedoStack && this.brushRedoStack.length > 0) {
        const stroke = this.brushRedoStack.pop();
        this.brushStrokes.push(stroke);
        this.renderCanvas();
        wx.showToast({ title: '已恢复笔画', icon: 'none', duration: 800 });
      } else {
        wx.showToast({ title: '无可前进内容', icon: 'none' });
      }
      return;
    }
    if (this.elementRedoStack && this.elementRedoStack.length > 0) {
      const el = this.elementRedoStack.pop();
      this.elements.push(el);
      this.setData({
        selectedElementId: el.id,
        selectedScale: el.scale || 1.0,
        selectedRotate: el.rotation || 0
      });
      this.renderCanvas();
      wx.showToast({ title: '已恢复元素', icon: 'none', duration: 800 });
    } else if (this.brushRedoStack && this.brushRedoStack.length > 0) {
      const stroke = this.brushRedoStack.pop();
      this.brushStrokes.push(stroke);
      this.renderCanvas();
      wx.showToast({ title: '已恢复笔画', icon: 'none', duration: 800 });
    } else {
      wx.showToast({ title: '无可前进内容', icon: 'none' });
    }
  },

  // --- Apple 风格修图：裁剪与底图适配、调色与滤镜控制 ---
  setCropSubTab(e) {
    const tab = e.currentTarget.dataset.tab;
    this.setData({ cropSubTab: tab });
  },

  setBgFitMode(e) {
    const mode = e.currentTarget.dataset.mode;
    this.setData({ bgFitMode: mode });
    this.renderCanvas();
  },

  onBgScaleChange(e) {
    const val = Number(e.detail.value);
    this.setData({ bgScale: val });
    this.renderCanvas();
  },

  rotateBgImage() {
    const next = ((this.data.bgRotation || 0) + 90) % 360;
    this.setData({ bgRotation: next });
    this.renderCanvas();
  },

  flipBgImage() {
    this.setData({ bgFlipH: !this.data.bgFlipH });
    this.renderCanvas();
  },

  removeBgImage() {
    wx.showModal({
      title: '去掉图片',
      content: '确定要去掉底图，切换为纯白画板进行涂鸦创作吗？',
      confirmColor: '#ef4444',
      success: (res) => {
        if (res.confirm) {
          this.bgImageObj = null;
          this.setData({
            bgImageSrc: '',
            bgOffsetX: 0,
            bgOffsetY: 0,
            bgScale: 1.0,
            bgRotation: 0,
            bgFlipH: false
          });
          this.renderCanvas();
          wx.showToast({ title: '已清除底图', icon: 'none' });
        }
      }
    });
  },

  changeBgImage() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      success: (res) => {
        if (res.tempFiles && res.tempFiles.length > 0) {
          const path = res.tempFiles[0].tempFilePath;
          this.setData({
            bgImageSrc: path,
            bgOffsetX: 0,
            bgOffsetY: 0,
            bgScale: 1.0,
            bgRotation: 0,
            bgFlipH: false
          });
          wx.showLoading({ title: '载入新图片...' });
          const img = this.canvas.createImage();
          img.onload = () => {
            wx.hideLoading();
            this.bgImageObj = img;
            this.renderCanvas();
          };
          img.onerror = () => {
            wx.hideLoading();
            wx.showToast({ title: '加载图片失败', icon: 'none' });
          };
          img.src = path;
        }
      }
    });
  },

  onExposureChange(e) {
    this.setData({ imgExposure: Number(e.detail.value) });
    this.renderCanvas();
  },

  onContrastChange(e) {
    this.setData({ imgContrast: Number(e.detail.value) });
    this.renderCanvas();
  },

  onSaturationChange(e) {
    this.setData({ imgSaturation: Number(e.detail.value) });
    this.renderCanvas();
  },

  onBrightnessChange(e) {
    this.setData({ imgBrightness: Number(e.detail.value) });
    this.renderCanvas();
  },

  setImgFilter(e) {
    const f = e.currentTarget.dataset.filter;
    this.setData({ imgFilter: f });
    this.renderCanvas();
  },

  resetAdjust() {
    this.setData({
      imgExposure: 0,
      imgContrast: 0,
      imgSaturation: 0,
      imgBrightness: 0,
      imgFilter: 'original'
    });
    this.renderCanvas();
    wx.showToast({ title: '调色参数已重置', icon: 'none' });
  },

  // --- 交互式裁剪框触控与拖拽调整 ---
  onCropTouchStart(e) {
    const touch = e.touches[0];
    const handle = e.currentTarget.dataset.handle || 'body';
    this.cropTouchInfo = {
      startX: touch.clientX,
      startY: touch.clientY,
      handle: handle,
      initialBox: { ...this.data.cropBox }
    };
  },

  onCropTouchMove(e) {
    if (!this.cropTouchInfo) return;
    const touch = e.touches[0];
    const dx = touch.clientX - this.cropTouchInfo.startX;
    const dy = touch.clientY - this.cropTouchInfo.startY;
    const { handle, initialBox } = this.cropTouchInfo;
    const maxW = this.data.canvasWidth;
    const maxH = this.data.canvasHeight;
    const minSize = 40;

    let { x, y, w, h } = initialBox;

    if (handle === 'body') {
      x = Math.max(0, Math.min(initialBox.x + dx, maxW - w));
      y = Math.max(0, Math.min(initialBox.y + dy, maxH - h));
    } else {
      if (handle === 'tl') {
        x = Math.min(initialBox.x + dx, initialBox.x + initialBox.w - minSize);
        y = Math.min(initialBox.y + dy, initialBox.y + initialBox.h - minSize);
        x = Math.max(0, x);
        y = Math.max(0, y);
        w = initialBox.x + initialBox.w - x;
        h = initialBox.y + initialBox.h - y;
      } else if (handle === 'tr') {
        y = Math.min(initialBox.y + dy, initialBox.y + initialBox.h - minSize);
        y = Math.max(0, y);
        w = Math.max(minSize, Math.min(initialBox.w + dx, maxW - initialBox.x));
        h = initialBox.y + initialBox.h - y;
      } else if (handle === 'bl') {
        x = Math.min(initialBox.x + dx, initialBox.x + initialBox.w - minSize);
        x = Math.max(0, x);
        w = initialBox.x + initialBox.w - x;
        h = Math.max(minSize, Math.min(initialBox.h + dy, maxH - initialBox.y));
      } else if (handle === 'br') {
        w = Math.max(minSize, Math.min(initialBox.w + dx, maxW - initialBox.x));
        h = Math.max(minSize, Math.min(initialBox.h + dy, maxH - initialBox.y));
      } else if (handle === 't') {
        y = Math.min(initialBox.y + dy, initialBox.y + initialBox.h - minSize);
        y = Math.max(0, y);
        h = initialBox.y + initialBox.h - y;
      } else if (handle === 'b') {
        h = Math.max(minSize, Math.min(initialBox.h + dy, maxH - initialBox.y));
      } else if (handle === 'l') {
        x = Math.min(initialBox.x + dx, initialBox.x + initialBox.w - minSize);
        x = Math.max(0, x);
        w = initialBox.x + initialBox.w - x;
      } else if (handle === 'r') {
        w = Math.max(minSize, Math.min(initialBox.w + dx, maxW - initialBox.x));
      }

      const ratio = this.data.cropRatio;
      if (ratio && ratio !== 'free') {
        let r = 1;
        if (ratio === '1:1') r = 1;
        else if (ratio === '4:3') r = 4 / 3;
        else if (ratio === '3:4') r = 3 / 4;
        else if (ratio === '16:9') r = 16 / 9;

        if (handle === 't' || handle === 'b') {
          w = h * r;
        } else {
          h = w / r;
        }
        if (x + w > maxW) w = maxW - x;
        if (y + h > maxH) h = maxH - y;
      }
    }

    this.setData({
      cropBox: {
        x: Math.round(x),
        y: Math.round(y),
        w: Math.round(w),
        h: Math.round(h)
      }
    });
  },

  onCropTouchEnd() {
    this.cropTouchInfo = null;
  },

  resetCropBox() {
    const pad = 12;
    const w = this.data.canvasWidth - pad * 2;
    const h = this.data.canvasHeight - pad * 2;
    this.setData({
      cropBox: { x: pad, y: pad, w: w, h: h },
      cropRatio: 'free'
    });
  },

  setCropRatio(e) {
    const ratio = e.currentTarget.dataset.ratio;
    this.setData({ cropRatio: ratio });
    if (ratio === 'free') return;

    let r = 1;
    if (ratio === '1:1') r = 1;
    else if (ratio === '4:3') r = 4 / 3;
    else if (ratio === '3:4') r = 3 / 4;
    else if (ratio === '16:9') r = 16 / 9;

    const maxW = this.data.canvasWidth - 24;
    const maxH = this.data.canvasHeight - 24;
    let w = maxW;
    let h = w / r;
    if (h > maxH) {
      h = maxH;
      w = h * r;
    }
    const x = Math.round((this.data.canvasWidth - w) / 2);
    const y = Math.round((this.data.canvasHeight - h) / 2);

    this.setData({
      cropBox: { x, y, w: Math.round(w), h: Math.round(h) }
    });
  },

  // 确认裁剪：将当前裁剪选区输出并应用为新底图
  applyCrop() {
    if (!this.canvas || !this.data.bgImageSrc) {
      wx.showToast({ title: '暂无底图可裁剪', icon: 'none' });
      return;
    }

    const { x, y, w, h } = this.data.cropBox;
    if (w < 20 || h < 20) {
      wx.showToast({ title: '裁剪区域太小', icon: 'none' });
      return;
    }

    wx.showLoading({ title: '正在应用裁剪...' });
    this.setData({ selectedElementId: null });
    this.renderCanvas();

    setTimeout(() => {
      wx.canvasToTempFilePath({
        canvas: this.canvas,
        x: Math.round(x),
        y: Math.round(y),
        width: Math.round(w),
        height: Math.round(h),
        destWidth: Math.round(w * this.dpr),
        destHeight: Math.round(h * this.dpr),
        fileType: 'png',
        quality: 1,
        success: (res) => {
          wx.hideLoading();
          const croppedSrc = res.tempFilePath;
          this.elementRedoStack = [];
          this.setData({
            bgImageSrc: croppedSrc,
            bgOffsetX: 0,
            bgOffsetY: 0,
            bgScale: 1.0,
            bgRotation: 0,
            bgFlipH: false
          });
          this.initCanvas(croppedSrc);
          this.resetCropBox();
          wx.showToast({ title: '裁剪已应用！', icon: 'success' });
        },
        fail: (err) => {
          wx.hideLoading();
          console.error("裁剪导出失败:", err);
          wx.showToast({ title: '裁剪失败，请重试', icon: 'none' });
        }
      });
    }, 120);
  },

  resetCrop() {
    this.setData({
      bgFitMode: 'cover',
      bgScale: 1.0,
      bgOffsetX: 0,
      bgOffsetY: 0,
      bgRotation: 0,
      bgFlipH: false
    });
    this.renderCanvas();
    this.resetCropBox();
    wx.showToast({ title: '构图已重置', icon: 'none' });
  },

  // --- 保存到手机相册 ---
  saveToAlbum() {
    if (!this.canvas) return;
    this.setData({ selectedElementId: null });
    this.renderCanvas();

    wx.showLoading({ title: '正在导出相册...' });
    setTimeout(() => {
      wx.canvasToTempFilePath({
        canvas: this.canvas,
        fileType: 'png',
        quality: 1,
        success: (res) => {
          wx.hideLoading();
          if (res.tempFilePath) {
            wx.saveImageToPhotosAlbum({
              filePath: res.tempFilePath,
              success: () => {
                wx.showToast({ title: '已保存至手机相册！', icon: 'success' });
              },
              fail: () => {
                wx.showToast({ title: '保存失败，请授权相册权限', icon: 'none' });
              }
            });
          }
        },
        fail: () => {
          wx.hideLoading();
          wx.showToast({ title: '导出失败', icon: 'none' });
        }
      });
    }, 150);
  },

  clearAll() {
    wx.showModal({
      title: '清空画布',
      content: '确定要清空所有贴纸、文字和涂鸦吗？',
      success: (res) => {
        if (res.confirm) {
          this.elements = [];
          this.brushStrokes = [];
          this.brushRedoStack = [];
          this.elementRedoStack = [];
          this.setData({ selectedElementId: null });
          this.renderCanvas();
        }
      }
    });
  },

  getCanvasCenter() {
    return {
      x: this.data.canvasWidth / 2,
      y: this.data.canvasHeight / 2
    };
  },

  // --- 完成编辑并导出 ---
  finishAndApply() {
    if (!this.canvas) return;
    // 取消选中框以便干净导出
    this.setData({ selectedElementId: null });
    this.renderCanvas();

    wx.showLoading({ title: '正在导出合成图...' });

    setTimeout(() => {
      wx.canvasToTempFilePath({
        canvas: this.canvas,
        fileType: 'png',
        quality: 1,
        success: (res) => {
          wx.hideLoading();
          const savedPath = res.tempFilePath;
          // 保存至全局供 index.js 自动取用
          app.globalData.tempEditedImage = savedPath;
          wx.showToast({ title: '修图完成已应用！', icon: 'success' });
          setTimeout(() => {
            wx.navigateBack();
          }, 400);
        },
        fail: (err) => {
          wx.hideLoading();
          console.error("导出画布失败:", err);
          wx.showToast({ title: '导出失败，请重试', icon: 'none' });
        }
      });
    }, 150);
  },

  goBack() {
    wx.navigateBack();
  }
});
