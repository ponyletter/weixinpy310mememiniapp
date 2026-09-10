document.addEventListener("DOMContentLoaded", () => {
  // ==========================================
  // 全局状态
  // ==========================================
  let currentTemplateId = "kiss";
  let templatesData = [];
  let selectedRefImage = null;       // 模式 1：参考角色图片 (可选)
  let selectedSpriteFile = null;     // 模式 2：已有 4x4 精灵图
  let selectedSampleId = null;       // 模式 2：内置测试样本
  let progressInterval = null;

  // ==========================================
  // DOM 元素引用
  // ==========================================
  // 模式切换
  const tabModeAI = document.getElementById("tabModeAI");
  const tabModeSlicer = document.getElementById("tabModeSlicer");
  const panelAI = document.getElementById("panelAI");
  const panelSlicer = document.getElementById("panelSlicer");

  // 模式 1：AI 生图
  const refDropZone = document.getElementById("refDropZone");
  const refImageInput = document.getElementById("refImageInput");
  const refPlaceholder = document.getElementById("refPlaceholder");
  const refPreviewContainer = document.getElementById("refPreviewContainer");
  const refPreviewImg = document.getElementById("refPreviewImg");
  const btnRemoveRef = document.getElementById("btnRemoveRef");
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

  // 等待交互区 (tqdm + 贪吃蛇)
  const waitingCard = document.getElementById("waitingCard");
  const tqdmStageText = document.getElementById("tqdmStageText");
  const tqdmPercentText = document.getElementById("tqdmPercentText");
  const tqdmBarFill = document.getElementById("tqdmBarFill");
  const tqdmTime = document.getElementById("tqdmTime");

  // 结果展示区
  const resultCard = document.getElementById("resultCard");
  const gifImage = document.getElementById("gifImage");
  const statFrames = document.getElementById("statFrames");
  const statSize = document.getElementById("statSize");
  const statDuration = document.getElementById("statDuration");
  const statAlpha = document.getElementById("statAlpha");
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
  // 2. 模式 1：参考角色图片上传与移除
  // ==========================================
  refDropZone.addEventListener("click", (e) => {
    if (e.target !== btnRemoveRef) {
      refImageInput.click();
    }
  });

  refImageInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
      handleRefFile(e.target.files[0]);
    }
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
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleRefFile(e.dataTransfer.files[0]);
    }
  });

  function handleRefFile(file) {
    if (!file.type.startsWith("image/")) {
      alert("请上传有效的图片格式 (JPG/PNG)");
      return;
    }
    selectedRefImage = file;
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
  // 3. 模式 1：动作模板加载与字幕处理
  // ==========================================
  fetch("/api/templates")
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

    fetch("/api/prompt-builder", {
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

  // 参数面板折叠
  toggleAdvParams.addEventListener("click", () => {
    const isHidden = advParamsContent.style.display === "none";
    advParamsContent.style.display = isHidden ? "block" : "none";
    advArrow.classList.toggle("open", isHidden);
  });

  fpsRangeAI.addEventListener("input", (e) => {
    fpsValAI.textContent = e.target.value;
  });

  // ==========================================
  // 4. 模式 2：已有精灵图切片
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
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleSpriteFile(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
      handleSpriteFile(e.target.files[0]);
    }
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
      const resp = await fetch("/api/process-sprite", {
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
  // 5. 启动 AI 生图 + tqdm 进度条 + 贪吃蛇激活 (异步轮询模式，零超时)
  // ==========================================
  let pollInterval = null;

  btnAIGenerate.addEventListener("click", async () => {
    btnAIGenerate.disabled = true;

    // 显示等待卡片并滚动到此
    waitingCard.style.display = "block";
    resultCard.style.display = "none";
    waitingCard.scrollIntoView({ behavior: "smooth" });

    // 初始化进度条与小游戏
    startTqdmProgress();
    startSnakeGame();

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

    try {
      // 1. 发起异步任务创建 (仅需 20ms)
      const startResp = await fetch("/api/generate-async", {
        method: "POST",
        body: formData
      });
      const startJson = await startResp.json();

      if (startJson.code !== 0 || !startJson.data || !startJson.data.task_id) {
        throw new Error(startJson.message || "创建生成任务失败");
      }

      const taskId = startJson.data.task_id;
      let startTime = Date.now();

      // 2. 轮询任务状态 (每 1.5 秒一次，毫秒级轻量，绝无连接超时风险)
      clearInterval(pollInterval);
      pollInterval = setInterval(async () => {
        try {
          const statusResp = await fetch(`/api/task-status/${taskId}?t=${Date.now()}`);
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
            finishTqdmProgress();
            setTimeout(() => {
              waitingCard.style.display = "none";
              displayResults(task.data);
              btnAIGenerate.disabled = false;
            }, 1000);
          } else if (task.status === "failed") {
            clearInterval(pollInterval);
            clearInterval(progressInterval);
            alert("AI 出图失败: " + (task.error || "未知异常"));
            waitingCard.style.display = "none";
            btnAIGenerate.disabled = false;
          }
        } catch (pollErr) {
          console.warn("轮询状态中...", pollErr);
        }
      }, 1500);

    } catch (err) {
      clearInterval(pollInterval);
      clearInterval(progressInterval);
      alert("启动生成任务异常: " + err.message);
      waitingCard.style.display = "none";
      btnAIGenerate.disabled = false;
    }
  });

  // tqdm 进度条逻辑
  function startTqdmProgress() {
    let seconds = 0;
    const estTotal = 32;
    tqdmBarFill.style.width = "5%";
    tqdmPercentText.textContent = "5%";
    tqdmStageText.textContent = "阶段 1/4: 组装角色提示词与姿态参数...";
    tqdmTime.textContent = `耗时: 0s / 预计 ${estTotal}s`;

    clearInterval(progressInterval);
    progressInterval = setInterval(() => {
      seconds++;
      let percent = Math.min(92, Math.round((seconds / estTotal) * 100));

      if (seconds < 3) {
        tqdmStageText.textContent = "阶段 1/4: 组装角色提示词与人设语义对齐...";
      } else if (seconds < 26) {
        tqdmStageText.textContent = "阶段 2/4: ChatGPT Plus (Images 2.5) 正在逐帧绘制 16 宫格雪碧图...";
      } else if (seconds < 30) {
        tqdmStageText.textContent = "阶段 3/4: 多尺度主间隙投影网格切割与角色包络裁剪...";
      } else {
        tqdmStageText.textContent = "阶段 4/4: 固定色差泛洪去底并封装微信 GIF 动图...";
      }

      tqdmBarFill.style.width = `${percent}%`;
      tqdmPercentText.textContent = `${percent}%`;
      tqdmTime.textContent = `耗时: ${seconds}s / 预计 ${estTotal}s`;
    }, 1000);
  }

  function finishTqdmProgress() {
    clearInterval(progressInterval);
    tqdmBarFill.style.width = "100%";
    tqdmPercentText.textContent = "100%";
    tqdmStageText.textContent = "🎉 制作全部完成！正在导出动图预览...";
  }

  // ==========================================
  // 6. 结果渲染
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
  // 7. 贪吃蛇小游戏 (Retro Canvas Snake)
  // ==========================================
  const snakeCanvas = document.getElementById("snakeCanvas");
  const ctx = snakeCanvas.getContext("2d");
  const btnStartSnake = document.getElementById("btnStartSnake");
  const snakeOverlay = document.getElementById("snakeOverlay");
  const snakeCurrentScore = document.getElementById("snakeCurrentScore");
  const snakeHighScore = document.getElementById("snakeHighScore");

  const CELL_SIZE = 10;
  const COLS = snakeCanvas.width / CELL_SIZE;
  const ROWS = snakeCanvas.height / CELL_SIZE;

  let snake = [];
  let food = { x: 0, y: 0 };
  let dir = { x: 1, y: 0 };
  let nextDir = { x: 1, y: 0 };
  let score = 0;
  let highScore = parseInt(localStorage.getItem("meme_snake_highscore") || "0", 10);
  let snakeTimer = null;
  let gameRunning = false;

  snakeHighScore.textContent = highScore;

  btnStartSnake.addEventListener("click", startSnakeGame);

  function startSnakeGame() {
    snake = [
      { x: 10, y: 10 },
      { x: 9, y: 10 },
      { x: 8, y: 10 }
    ];
    dir = { x: 1, y: 0 };
    nextDir = { x: 1, y: 0 };
    score = 0;
    snakeCurrentScore.textContent = score;
    spawnFood();
    gameRunning = true;
    snakeOverlay.style.display = "none";

    clearInterval(snakeTimer);
    snakeTimer = setInterval(gameLoop, 90);
  }

  function spawnFood() {
    food = {
      x: Math.floor(Math.random() * COLS),
      y: Math.floor(Math.random() * ROWS)
    };
    // 避免生成在蛇身上
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

    // 撞墙穿透循环 (经典街机风)
    if (head.x < 0) head.x = COLS - 1;
    if (head.x >= COLS) head.x = 0;
    if (head.y < 0) head.y = ROWS - 1;
    if (head.y >= ROWS) head.y = 0;

    // 撞自身检测
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
      if (score > highScore) {
        highScore = score;
        snakeHighScore.textContent = highScore;
        localStorage.setItem("meme_snake_highscore", highScore);
      }
      spawnFood();
    } else {
      snake.pop();
    }

    drawSnake();
  }

  function drawSnake() {
    ctx.fillStyle = "#090d16";
    ctx.fillRect(0, 0, snakeCanvas.width, snakeCanvas.height);

    // 画食物 (发光红苹果)
    ctx.fillStyle = "#ef4444";
    ctx.shadowBlur = 8;
    ctx.shadowColor = "#ef4444";
    ctx.beginPath();
    ctx.arc(food.x * CELL_SIZE + CELL_SIZE/2, food.y * CELL_SIZE + CELL_SIZE/2, CELL_SIZE/2 - 1, 0, Math.PI * 2);
    ctx.fill();

    // 画蛇
    snake.forEach((seg, idx) => {
      ctx.fillStyle = idx === 0 ? "#10b981" : "#34d399";
      ctx.shadowBlur = idx === 0 ? 6 : 0;
      ctx.shadowColor = "#10b981";
      ctx.fillRect(seg.x * CELL_SIZE + 1, seg.y * CELL_SIZE + 1, CELL_SIZE - 2, CELL_SIZE - 2);
    });

    ctx.shadowBlur = 0;
  }

  function gameOver() {
    clearInterval(snakeTimer);
    gameRunning = false;
    snakeOverlay.style.display = "flex";
    btnStartSnake.innerText = `💥 游戏结束 (得分: ${score})，点击重来`;
  }

  // 键盘控制
  window.addEventListener("keydown", (e) => {
    if (!gameRunning) return;
    if (["ArrowUp", "KeyW"].includes(e.code) && dir.y === 0) nextDir = { x: 0, y: -1 };
    if (["ArrowDown", "KeyS"].includes(e.code) && dir.y === 0) nextDir = { x: 0, y: 1 };
    if (["ArrowLeft", "KeyA"].includes(e.code) && dir.x === 0) nextDir = { x: -1, y: 0 };
    if (["ArrowRight", "KeyD"].includes(e.code) && dir.x === 0) nextDir = { x: 1, y: 0 };
  });

  // 虚拟十字按键控制 (手机端)
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
