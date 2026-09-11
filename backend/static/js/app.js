document.addEventListener("DOMContentLoaded", () => {
  // ==========================================
  // 全局状态
  // ==========================================
  let currentTemplateId = "kiss";
  let templatesData = [];
  let selectedRefImage = null;       // 模式 1：参考角色图片 (文件或草图导出)
  let isSketchMode = false;          // 是否为 ChatGPT Images 2.5 手绘草图模式
  let selectedSpriteFile = null;     // 模式 2：已有 4x4 精灵图
  let selectedSampleId = null;       // 模式 2：内置测试样本
  let progressInterval = null;
  let pollInterval = null;
  let accessToken = "";

  // The H5 console is a development tool. The backend only accepts this mock login in DEBUG mode.
  const authReady = window.fetch("/api/user/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code: "mock_h5_console" })
  }).then(async response => {
    if (!response.ok) throw new Error("H5 调试登录不可用，请确认后端 DEBUG=true");
    const data = await response.json();
    accessToken = data.access_token;
  });

  async function apiFetch(url, options = {}) {
    await authReady;
    const headers = new Headers(options.headers || {});
    headers.set("Authorization", `Bearer ${accessToken}`);
    return window.fetch(url, { ...options, headers });
  }

  // ==========================================
  // DOM 元素引用
  // ==========================================
  // 模式切换
  const tabModeAI = document.getElementById("tabModeAI");
  const tabModeSlicer = document.getElementById("tabModeSlicer");
  const panelAI = document.getElementById("panelAI");
  const panelSlicer = document.getElementById("panelSlicer");

  // 模式 1：人设来源切换 (上传图 vs 手绘草图)
  const btnSourceUpload = document.getElementById("btnSourceUpload");
  const btnSourceSketch = document.getElementById("btnSourceSketch");
  const boxUploadRef = document.getElementById("boxUploadRef");
  const boxSketchRef = document.getElementById("boxSketchRef");

  // 图片上传元素
  const refDropZone = document.getElementById("refDropZone");
  const refImageInput = document.getElementById("refImageInput");
  const refPlaceholder = document.getElementById("refPlaceholder");
  const refPreviewContainer = document.getElementById("refPreviewContainer");
  const refPreviewImg = document.getElementById("refPreviewImg");
  const btnRemoveRef = document.getElementById("btnRemoveRef");

  // 草图画板元素
  const sketchCanvas = document.getElementById("sketchCanvas");
  const sketchCtx = sketchCanvas ? sketchCanvas.getContext("2d") : null;
  const toolPencil = document.getElementById("toolPencil");
  const toolEraser = document.getElementById("toolEraser");
  const btnUndoSketch = document.getElementById("btnUndoSketch");
  const btnClearSketch = document.getElementById("btnClearSketch");
  const sketchStatusText = document.getElementById("sketchStatusText");
  const colorDots = document.querySelectorAll(".color-dot");

  // 提示词 & 动作
  const charDescInput = document.getElementById("charDesc");
  const templateGrid = document.getElementById("templateGrid");
  const captionInput = document.getElementById("captionInput");
  const btnClearCaption = document.getElementById("btnClearCaption");
  const toggleAdvParams = document.getElementById("toggleAdvParams");
  const advParamsContent = document.getElementById("advParamsContent");
  const advArrow = document.getElementById("advArrow");
  const padSelectAI = document.getElementById("padSelectAI");
  const fpsRangeAI = document.getElementById("fpsRangeAI");
  const fpsValAI = document.getElementById("fpsValAI");
  const chkTransparentAI = document.getElementById("chkTransparentAI");
  const promptOutput = document.getElementById("promptOutput");
  const btnCopyPrompt = document.getElementById("btnCopyPrompt");
  const btnAIGenerate = document.getElementById("btnAIGenerate");

  // 模式 2：精灵图切片
  const dropZone = document.getElementById("dropZone");
  const fileInput = document.getElementById("fileInput");
  const fileNameDisplay = document.getElementById("fileNameDisplay");
  const btnUseSample = document.getElementById("btnUseSample");
  const padSelectSlicer = document.getElementById("padSelectSlicer");
  const fpsRangeSlicer = document.getElementById("fpsRangeSlicer");
  const fpsValSlicer = document.getElementById("fpsValSlicer");
  const chkTransparentSlicer = document.getElementById("chkTransparentSlicer");
  const btnProcess = document.getElementById("btnProcess");

  // 等待交互区 (tqdm + 棋盘格彩蛋游戏)
  const waitingCard = document.getElementById("waitingCard");
  const tqdmStageText = document.getElementById("tqdmStageText");
  const tqdmPercentText = document.getElementById("tqdmPercentText");
  const tqdmBarFill = document.getElementById("tqdmBarFill");
  const tqdmTime = document.getElementById("tqdmTime");
  const triggerEggArea = document.getElementById("triggerEggArea");
  const compactLoadingState = document.getElementById("compactLoadingState");
  const snakeGameBox = document.getElementById("snakeGameBox");
  const btnCloseEgg = document.getElementById("btnCloseEgg");

  // 结果展示区
  const resultCard = document.getElementById("resultCard");
  const gifImage = document.getElementById("gifImage");
  const statFrames = document.getElementById("statFrames");
  const statSize = document.getElementById("statSize");
  const statDuration = document.getElementById("statDuration");
  const btnDownloadGif = document.getElementById("btnDownloadGif");
  const btnDownloadZip = document.getElementById("btnDownloadZip");
  const framesGrid = document.getElementById("framesGrid");

  // ==========================================
  // 1. 模式 Tab 切换
  // ==========================================
  tabModeAI.addEventListener("click", () => {
    tabModeAI.classList.add("active");
    tabModeSlicer.classList.remove("active");
    panelAI.style.display = "block";
    panelSlicer.style.display = "none";
  });

  tabModeSlicer.addEventListener("click", () => {
    tabModeSlicer.classList.add("active");
    tabModeAI.classList.remove("active");
    panelSlicer.style.display = "block";
    panelAI.style.display = "none";
  });

  // ==========================================
  // 2. 人设来源切换 (上传图片 vs 在线手绘草图)
  // ==========================================
  btnSourceUpload.addEventListener("click", () => {
    btnSourceUpload.classList.add("active");
    btnSourceSketch.classList.remove("active");
    boxUploadRef.style.display = "block";
    boxSketchRef.style.display = "none";
    isSketchMode = false;
    updatePrompt();
  });

  btnSourceSketch.addEventListener("click", () => {
    btnSourceSketch.classList.add("active");
    btnSourceUpload.classList.remove("active");
    boxSketchRef.style.display = "block";
    boxUploadRef.style.display = "none";
    isSketchMode = true;
    initSketchCanvasOnce();
    syncSketchToRefImage();
    updatePrompt();
  });

  // 上传图片处理
  refDropZone.addEventListener("click", (e) => {
    if (e.target !== btnRemoveRef) refImageInput.click();
  });

  refImageInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) handleRefFile(e.target.files[0]);
  });

  refDropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    refDropZone.style.borderColor = "#6366f1";
  });
  refDropZone.addEventListener("dragleave", () => {
    refDropZone.style.borderColor = "#cbd5e1";
  });
  refDropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    refDropZone.style.borderColor = "#cbd5e1";
    if (e.dataTransfer.files && e.dataTransfer.files[0]) handleRefFile(e.dataTransfer.files[0]);
  });

  function handleRefFile(file) {
    if (!file.type.startsWith("image/")) {
      alert("请上传有效的图片格式 (JPG/PNG)");
      return;
    }
    selectedRefImage = file;
    isSketchMode = false;
    const reader = new FileReader();
    reader.onload = (e) => {
      refPreviewImg.src = e.target.result;
      refPlaceholder.style.display = "none";
      refPreviewContainer.style.display = "block";
      updatePrompt();
    };
    reader.readAsDataURL(file);
  }

  btnRemoveRef.addEventListener("click", (e) => {
    e.stopPropagation();
    selectedRefImage = null;
    refImageInput.value = "";
    refPreviewImg.src = "";
    refPreviewContainer.style.display = "none";
    refPlaceholder.style.display = "flex";
    updatePrompt();
  });

  // ==========================================
  // 3. ChatGPT Images 2.5 在线手绘草图引擎 (Sketch Board)
  // ==========================================
  let isDrawing = false;
  let sketchTool = "pencil";
  let currentColor = "#1e293b";
  let sketchHistory = [];
  let sketchInitialized = false;

  function initSketchCanvasOnce() {
    if (sketchInitialized || !sketchCtx) return;
    sketchInitialized = true;

    // 初始化画板为纯白色背景
    sketchCtx.fillStyle = "#ffffff";
    sketchCtx.fillRect(0, 0, sketchCanvas.width, sketchCanvas.height);
    saveSketchState();

    // 绑定鼠标事件
    sketchCanvas.addEventListener("mousedown", startDrawing);
    sketchCanvas.addEventListener("mousemove", draw);
    sketchCanvas.addEventListener("mouseup", stopDrawing);
    sketchCanvas.addEventListener("mouseleave", stopDrawing);

    // 绑定触屏手势
    sketchCanvas.addEventListener("touchstart", (e) => {
      e.preventDefault();
      const touch = e.touches[0];
      const rect = sketchCanvas.getBoundingClientRect();
      startDrawing({ offsetX: touch.clientX - rect.left, offsetY: touch.clientY - rect.top });
    }, { passive: false });

    sketchCanvas.addEventListener("touchmove", (e) => {
      e.preventDefault();
      const touch = e.touches[0];
      const rect = sketchCanvas.getBoundingClientRect();
      draw({ offsetX: touch.clientX - rect.left, offsetY: touch.clientY - rect.top });
    }, { passive: false });

    sketchCanvas.addEventListener("touchend", stopDrawing);
  }

  function startDrawing(e) {
    isDrawing = true;
    sketchCtx.beginPath();
    sketchCtx.moveTo(e.offsetX, e.offsetY);
    draw(e);
  }

  function draw(e) {
    if (!isDrawing) return;
    sketchCtx.lineCap = "round";
    sketchCtx.lineJoin = "round";

    if (sketchTool === "eraser") {
      sketchCtx.strokeStyle = "#ffffff";
      sketchCtx.lineWidth = 14;
    } else {
      sketchCtx.strokeStyle = currentColor;
      sketchCtx.lineWidth = 3.5;
    }

    sketchCtx.lineTo(e.offsetX, e.offsetY);
    sketchCtx.stroke();
  }

  function stopDrawing() {
    if (isDrawing) {
      isDrawing = false;
      sketchCtx.closePath();
      saveSketchState();
      syncSketchToRefImage();
    }
  }

  function saveSketchState() {
    if (!sketchCtx) return;
    sketchHistory.push(sketchCtx.getImageData(0, 0, sketchCanvas.width, sketchCanvas.height));
    if (sketchHistory.length > 20) sketchHistory.shift();
  }

  // 工具切换：画笔 vs 橡皮
  if (toolPencil) {
    toolPencil.addEventListener("click", () => {
      sketchTool = "pencil";
      toolPencil.classList.add("active");
      toolEraser.classList.remove("active");
    });
  }

  if (toolEraser) {
    toolEraser.addEventListener("click", () => {
      sketchTool = "eraser";
      toolEraser.classList.add("active");
      toolPencil.classList.remove("active");
    });
  }

  // 颜色点切换
  colorDots.forEach(dot => {
    dot.addEventListener("click", () => {
      colorDots.forEach(d => d.classList.remove("active"));
      dot.classList.add("active");
      currentColor = dot.getAttribute("data-color");
      if (sketchTool === "eraser") {
        sketchTool = "pencil";
        toolPencil.classList.add("active");
        toolEraser.classList.remove("active");
      }
    });
  });

  // 撤销
  if (btnUndoSketch) {
    btnUndoSketch.addEventListener("click", () => {
      if (sketchHistory.length > 1) {
        sketchHistory.pop();
        const prev = sketchHistory[sketchHistory.length - 1];
        sketchCtx.putImageData(prev, 0, 0);
        syncSketchToRefImage();
      }
    });
  }

  // 清空画板
  if (btnClearSketch) {
    btnClearSketch.addEventListener("click", () => {
      sketchCtx.fillStyle = "#ffffff";
      sketchCtx.fillRect(0, 0, sketchCanvas.width, sketchCanvas.height);
      saveSketchState();
      selectedRefImage = null;
      sketchStatusText.textContent = "画板已清空";
      updatePrompt();
    });
  }

  // 将 Canvas 实时导出为图片供后端 API 使用
  function syncSketchToRefImage() {
    if (!sketchCanvas) return;
    sketchCanvas.toBlob((blob) => {
      if (blob) {
        selectedRefImage = new File([blob], "sketch_character.png", { type: "image/png" });
        sketchStatusText.textContent = "✓ 草图已同步，将按草图精绘";
        updatePrompt();
      }
    }, "image/png");
  }

  // ==========================================
  // 4. 动作模板与提示词处理
  // ==========================================
  apiFetch("/api/templates")
    .then(res => res.json())
    .then(data => {
      if (data.code === 0 && data.data) {
        templatesData = data.data;
        renderTemplates();
        updatePrompt();
      }
    })
    .catch(err => console.error("加载动作模板失败:", err));

  function renderTemplates() {
    templateGrid.innerHTML = "";
    templatesData.forEach(tpl => {
      const card = document.createElement("div");
      card.className = `tpl-card ${tpl.id === currentTemplateId ? "selected" : ""}`;
      card.innerHTML = `
        <div class="tpl-title">${tpl.title}</div>
        <div class="tpl-desc">${tpl.desc}</div>
      `;
      card.addEventListener("click", () => {
        currentTemplateId = tpl.id;
        document.querySelectorAll(".tpl-card").forEach(c => c.classList.remove("selected"));
        card.classList.add("selected");
        if (!captionInput.value || captionInput.getAttribute("data-auto") === "true") {
          captionInput.value = tpl.default_caption;
          captionInput.setAttribute("data-auto", "true");
        }
        updatePrompt();
      });
      templateGrid.appendChild(card);
    });

    const initTpl = templatesData.find(t => t.id === currentTemplateId);
    if (initTpl && !captionInput.value) {
      captionInput.value = initTpl.default_caption;
      captionInput.setAttribute("data-auto", "true");
    }
  }

  btnClearCaption.addEventListener("click", () => {
    captionInput.value = "";
    captionInput.removeAttribute("data-auto");
    updatePrompt();
  });

  captionInput.addEventListener("input", () => {
    captionInput.removeAttribute("data-auto");
    updatePrompt();
  });

  charDescInput.addEventListener("input", updatePrompt);

  function updatePrompt() {
    const formData = new FormData();
    formData.append("action_type", currentTemplateId);
    formData.append("custom_caption", captionInput.value.trim());
    formData.append("character_desc", charDescInput.value.trim());
    formData.append("has_image", selectedRefImage !== null);
    formData.append("is_sketch", isSketchMode && selectedRefImage !== null);

    apiFetch("/api/prompt-builder", {
      method: "POST",
      body: formData
    })
      .then(res => res.json())
      .then(res => {
        if (res.code === 0 && res.data) {
          promptOutput.value = res.data.generated_prompt;
        }
      })
      .catch(err => console.error("生成提示词失败:", err));
  }

  btnCopyPrompt.addEventListener("click", () => {
    navigator.clipboard.writeText(promptOutput.value).then(() => {
      btnCopyPrompt.innerText = "✓ 已复制到剪贴板";
      setTimeout(() => btnCopyPrompt.innerText = "一键复制提示词", 2000);
    });
  });

  toggleAdvParams.addEventListener("click", () => {
    const isHidden = advParamsContent.style.display === "none";
    advParamsContent.style.display = isHidden ? "block" : "none";
    advArrow.classList.toggle("open", isHidden);
  });

  fpsRangeAI.addEventListener("input", (e) => {
    fpsValAI.textContent = e.target.value;
  });

  // ==========================================
  // 5. 模式 2：已有精灵图切片
  // ==========================================
  dropZone.addEventListener("click", () => fileInput.click());
  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files[0]) handleSpriteFile(e.dataTransfer.files[0]);
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) handleSpriteFile(e.target.files[0]);
  });

  function handleSpriteFile(file) {
    selectedSpriteFile = file;
    selectedSampleId = null;
    fileNameDisplay.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    btnUseSample.classList.remove("btn-primary");
    btnUseSample.classList.add("btn-outline");
  }

  btnUseSample.addEventListener("click", () => {
    selectedSpriteFile = null;
    fileInput.value = "";
    selectedSampleId = "kiss_sample";
    fileNameDisplay.textContent = "已就绪：内置【飞吻 16 帧 1024×1024】高保真样本";
    btnUseSample.classList.remove("btn-outline");
    btnUseSample.classList.add("btn-primary");
  });

  fpsRangeSlicer.addEventListener("input", (e) => {
    fpsValSlicer.textContent = e.target.value;
  });

  btnProcess.addEventListener("click", async () => {
    if (!selectedSpriteFile && !selectedSampleId) {
      alert("请先上传一张 4×4 精灵图，或点击【载入飞吻16帧测试样本】！");
      return;
    }

    const origBtnText = btnProcess.innerText;
    btnProcess.disabled = true;
    btnProcess.innerText = "⏳ 正在切片与去底合成中...";

    const formData = new FormData();
    if (selectedSpriteFile) {
      formData.append("file", selectedSpriteFile);
    } else if (selectedSampleId) {
      formData.append("sample_id", selectedSampleId);
    }
    formData.append("fps", fpsRangeSlicer.value);
    formData.append("make_transparent", chkTransparentSlicer.checked);
    formData.append("padding_percent", padSelectSlicer.value);

    try {
      const resp = await apiFetch("/api/process-sprite", {
        method: "POST",
        body: formData
      });
      const json = await resp.json();
      if (json.code === 0 && json.data) {
        displayResults(json.data);
      } else {
        alert("处理失败: " + (json.detail || json.message || "未知错误"));
      }
    } catch (err) {
      alert("请求异常: " + err.message);
    } finally {
      btnProcess.disabled = false;
      btnProcess.innerText = origBtnText;
    }
  });

  // ==========================================
  // 6. 启动 AI 生图 + tqdm 进度条 + 棋盘格彩蛋小游戏
  // ==========================================
  btnAIGenerate.addEventListener("click", async () => {
    btnAIGenerate.disabled = true;

    // 重置并显示等待卡片 (默认显示紧凑加载，小游戏隐藏节省空间)
    waitingCard.style.display = "block";
    resultCard.style.display = "none";
    compactLoadingState.style.display = "flex";
    snakeGameBox.style.display = "none";
    waitingCard.scrollIntoView({ behavior: "smooth" });

    // 启动 tqdm 进度条
    startTqdmProgress();

    const formData = new FormData();
    if (selectedRefImage) {
      formData.append("ref_image", selectedRefImage);
    }
    formData.append("action_type", currentTemplateId);
    formData.append("custom_caption", captionInput.value.trim());
    formData.append("character_desc", charDescInput.value.trim());
    formData.append("fps", fpsRangeAI.value);
    formData.append("make_transparent", chkTransparentAI.checked);
    formData.append("padding_percent", padSelectAI.value);
    formData.append("is_sketch", isSketchMode && selectedRefImage !== null);

    try {
      // 发起异步任务创建 (仅需 20ms)
      const startResp = await apiFetch("/api/generate-async", {
        method: "POST",
        body: formData
      });
      const startJson = await startResp.json();

      if (startJson.code !== 0 || !startJson.data || !startJson.data.task_id) {
        throw new Error(startJson.message || "创建生成任务失败");
      }

      const taskId = startJson.data.task_id;
      let startTime = Date.now();

      // 轮询任务状态 (每 1.5 秒一次，毫秒级轻量)
      clearInterval(pollInterval);
      pollInterval = setInterval(async () => {
        try {
          const statusResp = await apiFetch(`/api/task-status/${taskId}?t=${Date.now()}`);
          if (!statusResp.ok) return;
          const statusJson = await statusResp.json();
          if (statusJson.code !== 0 || !statusJson.data) return;

          const task = statusJson.data;
          const elapsedSec = Math.floor((Date.now() - startTime) / 1000);
          tqdmTime.textContent = `耗时: ${elapsedSec}s / 预计 32s`;

          if (task.status === "processing") {
            if (task.stage_text) tqdmStageText.textContent = task.stage_text;
            if (task.progress) {
              tqdmPercentText.textContent = `${task.progress}%`;
              tqdmBarFill.style.width = `${task.progress}%`;
            }
          } else if (task.status === "completed") {
            clearInterval(pollInterval);
            clearInterval(progressInterval);
            stopSnakeGame();
            finishTqdmProgress();
            setTimeout(() => {
              waitingCard.style.display = "none";
              displayResults(task.data);
              btnAIGenerate.disabled = false;
            }, 900);
          } else if (task.status === "failed") {
            clearInterval(pollInterval);
            clearInterval(progressInterval);
            stopSnakeGame();
            alert("AI 出图失败: " + (task.error || "未知异常"));
            waitingCard.style.display = "none";
            btnAIGenerate.disabled = false;
          }
        } catch (pollErr) {
          console.warn("轮询中...", pollErr);
        }
      }, 1500);

    } catch (err) {
      clearInterval(pollInterval);
      clearInterval(progressInterval);
      stopSnakeGame();
      alert("启动生成任务异常: " + err.message);
      waitingCard.style.display = "none";
      btnAIGenerate.disabled = false;
    }
  });

  // tqdm 进度条辅助函数
  function startTqdmProgress() {
    tqdmBarFill.style.width = "5%";
    tqdmPercentText.textContent = "5%";
    tqdmStageText.textContent = "阶段 1/4: 组装角色提示词与人设语义对齐...";
    tqdmTime.textContent = `耗时: 0s / 预计 32s`;
  }

  function finishTqdmProgress() {
    tqdmBarFill.style.width = "100%";
    tqdmPercentText.textContent = "100%";
    tqdmStageText.textContent = "🎉 制作全部完成！正在导出动图预览...";
  }

  // ==========================================
  // 7. 棋盘格点击展开 / 收起解闷彩蛋小游戏
  // ==========================================
  triggerEggArea.addEventListener("click", (e) => {
    // 如果已经在游戏中且不是点击收起按钮，不重复触发
    if (snakeGameBox.style.display === "block") return;
    compactLoadingState.style.display = "none";
    snakeGameBox.style.display = "block";
    startSnakeGame();
  });

  btnCloseEgg.addEventListener("click", (e) => {
    e.stopPropagation();
    stopSnakeGame();
    snakeGameBox.style.display = "none";
    compactLoadingState.style.display = "flex";
  });

  // ==========================================
  // 8. 结果渲染
  // ==========================================
  function displayResults(data) {
    resultCard.style.display = "block";
    resultCard.scrollIntoView({ behavior: "smooth" });

    const timestamp = new Date().getTime();
    gifImage.src = `${data.gif_url}?t=${timestamp}`;

    statFrames.textContent = `${data.stats.frame_count} 帧`;
    statSize.textContent = `${data.stats.file_size_kb} KB`;
    statDuration.textContent = `${data.stats.duration_per_frame_ms} ms / 帧`;

    btnDownloadGif.href = data.gif_url;
    btnDownloadZip.href = data.zip_url;

    framesGrid.innerHTML = "";
    data.frames.forEach((frameUrl, idx) => {
      const thumb = document.createElement("div");
      thumb.className = "frame-thumb";
      thumb.innerHTML = `
        <img src="${frameUrl}" alt="Frame ${idx + 1}">
        <div class="frame-idx">#${idx + 1}</div>
      `;
      framesGrid.appendChild(thumb);
    });
  }

  // ==========================================
  // 9. 贪吃蛇彩蛋小游戏逻辑
  // ==========================================
  const snakeCanvas = document.getElementById("snakeCanvas");
  const ctx = snakeCanvas ? snakeCanvas.getContext("2d") : null;
  const btnStartSnake = document.getElementById("btnStartSnake");
  const snakeOverlay = document.getElementById("snakeOverlay");
  const snakeCurrentScore = document.getElementById("snakeCurrentScore");

  const CELL_SIZE = 10;
  let COLS = 30;
  let ROWS = 18;

  let snake = [];
  let food = { x: 0, y: 0 };
  let dir = { x: 1, y: 0 };
  let nextDir = { x: 1, y: 0 };
  let score = 0;
  let snakeTimer = null;
  let gameRunning = false;

  if (snakeCanvas) {
    COLS = snakeCanvas.width / CELL_SIZE;
    ROWS = snakeCanvas.height / CELL_SIZE;
  }

  if (btnStartSnake) btnStartSnake.addEventListener("click", startSnakeGame);

  function startSnakeGame() {
    if (!ctx) return;
    snake = [
      { x: 10, y: 9 },
      { x: 9, y: 9 },
      { x: 8, y: 9 }
    ];
    dir = { x: 1, y: 0 };
    nextDir = { x: 1, y: 0 };
    score = 0;
    snakeCurrentScore.textContent = score;
    spawnFood();
    gameRunning = true;
    if (snakeOverlay) snakeOverlay.style.display = "none";

    clearInterval(snakeTimer);
    snakeTimer = setInterval(gameLoop, 95);
  }

  function stopSnakeGame() {
    clearInterval(snakeTimer);
    gameRunning = false;
  }

  function spawnFood() {
    food = {
      x: Math.floor(Math.random() * COLS),
      y: Math.floor(Math.random() * ROWS)
    };
    for (let segment of snake) {
      if (segment.x === food.x && segment.y === food.y) {
        spawnFood();
        break;
      }
    }
  }

  function gameLoop() {
    dir = nextDir;
    const head = { x: snake[0].x + dir.x, y: snake[0].y + dir.y };

    // 穿墙循环
    if (head.x < 0) head.x = COLS - 1;
    if (head.x >= COLS) head.x = 0;
    if (head.y < 0) head.y = ROWS - 1;
    if (head.y >= ROWS) head.y = 0;

    // 撞自身
    for (let segment of snake) {
      if (segment.x === head.x && segment.y === head.y) {
        gameOver();
        return;
      }
    }

    snake.unshift(head);

    // 吃到食物
    if (head.x === food.x && head.y === food.y) {
      score += 10;
      snakeCurrentScore.textContent = score;
      spawnFood();
    } else {
      snake.pop();
    }

    drawSnake();
  }

  function drawSnake() {
    ctx.fillStyle = "#090d16";
    ctx.fillRect(0, 0, snakeCanvas.width, snakeCanvas.height);

    // 画食物
    ctx.fillStyle = "#ef4444";
    ctx.beginPath();
    ctx.arc(food.x * CELL_SIZE + CELL_SIZE/2, food.y * CELL_SIZE + CELL_SIZE/2, CELL_SIZE/2 - 1, 0, Math.PI * 2);
    ctx.fill();

    // 画蛇
    snake.forEach((seg, idx) => {
      ctx.fillStyle = idx === 0 ? "#10b981" : "#34d399";
      ctx.fillRect(seg.x * CELL_SIZE + 1, seg.y * CELL_SIZE + 1, CELL_SIZE - 2, CELL_SIZE - 2);
    });
  }

  function gameOver() {
    stopSnakeGame();
    if (snakeOverlay) snakeOverlay.style.display = "flex";
    if (btnStartSnake) btnStartSnake.innerText = `💥 游戏结束 (得分: ${score})，点击重来`;
  }

  // 键盘方向控制
  window.addEventListener("keydown", (e) => {
    if (!gameRunning) return;
    if (["ArrowUp", "KeyW"].includes(e.code) && dir.y === 0) nextDir = { x: 0, y: -1 };
    if (["ArrowDown", "KeyS"].includes(e.code) && dir.y === 0) nextDir = { x: 0, y: 1 };
    if (["ArrowLeft", "KeyA"].includes(e.code) && dir.x === 0) nextDir = { x: -1, y: 0 };
    if (["ArrowRight", "KeyD"].includes(e.code) && dir.x === 0) nextDir = { x: 1, y: 0 };
  });

  // 手机触屏虚拟十字键
  document.querySelectorAll(".dpad-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      if (!gameRunning) startSnakeGame();
      const d = btn.getAttribute("data-dir");
      if (d === "up" && dir.y === 0) nextDir = { x: 0, y: -1 };
      if (d === "down" && dir.y === 0) nextDir = { x: 0, y: 1 };
      if (d === "left" && dir.x === 0) nextDir = { x: -1, y: 0 };
      if (d === "right" && dir.x === 0) nextDir = { x: 1, y: 0 };
    });
  });
});
