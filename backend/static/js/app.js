document.addEventListener("DOMContentLoaded", () => {
  // 状态变量
  let currentTemplateId = "kiss";
  let templatesData = [];
  let selectedFile = null;
  let selectedSampleId = null;

  // DOM 元素
  const templateGrid = document.getElementById("templateGrid");
  const charDescInput = document.getElementById("charDesc");
  const captionInput = document.getElementById("captionInput");
  const promptOutput = document.getElementById("promptOutput");
  const btnCopyPrompt = document.getElementById("btnCopyPrompt");

  const dropZone = document.getElementById("dropZone");
  const fileInput = document.getElementById("fileInput");
  const fileNameDisplay = document.getElementById("fileNameDisplay");
  const btnUseSample = document.getElementById("btnUseSample");

  const fpsRange = document.getElementById("fpsRange");
  const fpsVal = document.getElementById("fpsVal");
  const padSelect = document.getElementById("padSelect");
  const chkTransparent = document.getElementById("chkTransparent");
  const btnProcess = document.getElementById("btnProcess");


  const resultCard = document.getElementById("resultCard");
  const gifImage = document.getElementById("gifImage");
  const statFrames = document.getElementById("statFrames");
  const statSize = document.getElementById("statSize");
  const statDuration = document.getElementById("statDuration");
  const btnDownloadGif = document.getElementById("btnDownloadGif");
  const btnDownloadZip = document.getElementById("btnDownloadZip");
  const framesGrid = document.getElementById("framesGrid");

  // 1. 初始化拉取模板数据
  fetch("/api/templates")
    .then(res => res.json())
    .then(data => {
      if (data.code === 0 && data.data) {
        templatesData = data.data;
        renderTemplates();
        updatePrompt();
      }
    })
    .catch(err => console.error("加载模板失败:", err));

  // 渲染模板卡片
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

  // 动态更新 Prompt
  function updatePrompt() {
    const formData = new FormData();
    formData.append("character_desc", charDescInput.value);
    formData.append("action_type", currentTemplateId);
    formData.append("custom_caption", captionInput.value);

    fetch("/api/prompt-builder", {
      method: "POST",
      body: formData
    })
      .then(res => res.json())
      .then(res => {
        if (res.code === 0) {
          promptOutput.value = res.data.generated_prompt;
        }
      });
  }

  charDescInput.addEventListener("input", updatePrompt);
  captionInput.addEventListener("input", () => {
    captionInput.setAttribute("data-auto", "false");
    updatePrompt();
  });

  // 复制提示词
  btnCopyPrompt.addEventListener("click", () => {
    if (!promptOutput.value) return;
    navigator.clipboard.writeText(promptOutput.value)
      .then(() => {
        const orig = btnCopyPrompt.innerText;
        btnCopyPrompt.innerText = "✅ 已复制到剪贴板！";
        setTimeout(() => btnCopyPrompt.innerText = orig, 2000);
      })
      .catch(() => alert("复制失败，请手动长按复制文本框内容"));
  });

  // 2. 文件上传与拖拽
  dropZone.addEventListener("click", () => fileInput.click());

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  });

  function handleFile(file) {
    selectedFile = file;
    selectedSampleId = null;
    fileNameDisplay.textContent = `已选择本地图片: ${file.name} (${Math.round(file.size / 1024)} KB)`;
    btnUseSample.classList.remove("btn-primary");
    btnUseSample.classList.add("btn-outline");
  }

  // 使用测试样本按钮
  btnUseSample.addEventListener("click", () => {
    selectedFile = null;
    fileInput.value = "";
    selectedSampleId = "kiss_sample";
    fileNameDisplay.textContent = "已就绪：内置【飞吻 16 帧 1024×1024】高保真样本";
    btnUseSample.classList.remove("btn-outline");
    btnUseSample.classList.add("btn-primary");
  });

  // FPS 滑动条
  fpsRange.addEventListener("input", (e) => {
    fpsVal.textContent = e.target.value;
  });

  // 3. 执行切帧与动图合成
  btnProcess.addEventListener("click", async () => {
    if (!selectedFile && !selectedSampleId) {
      alert("请先上传一张 4×4 精灵图，或点击【载入飞吻16帧测试样本】！");
      return;
    }

    const origBtnText = btnProcess.innerText;
    btnProcess.disabled = true;
    btnProcess.innerText = "⏳ 正在极速执行 4×4 切帧与智能透明化合成中...";

    const formData = new FormData();
    if (selectedFile) {
      formData.append("file", selectedFile);
    } else if (selectedSampleId) {
      formData.append("sample_id", selectedSampleId);
    }
    formData.append("fps", fpsRange.value);
    formData.append("make_transparent", chkTransparent.checked);
    formData.append("padding_percent", padSelect.value);


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

  // 4. AI 一键出图并制作 GIF (调用 ChatGPT Plus 原生出图)
  const btnAIGenerate = document.getElementById("btnAIGenerate");
  const aiLoadingStatus = document.getElementById("aiLoadingStatus");

  if (btnAIGenerate) {
    btnAIGenerate.addEventListener("click", async () => {
      const origText = btnAIGenerate.innerText;
      btnAIGenerate.disabled = true;
      btnAIGenerate.innerText = "⏳ 正在通过海外 Plus 账号生图中 (约需 25~35 秒)...";
      if (aiLoadingStatus) aiLoadingStatus.style.display = "block";

      const formData = new FormData();
      formData.append("action_type", currentTemplateId);
      formData.append("custom_caption", captionInput.value.trim());
      formData.append("character_desc", charDescInput.value.trim());
      formData.append("fps", fpsRange.value);
      formData.append("make_transparent", chkTransparent.checked);
      formData.append("padding_percent", padSelect.value);

      try {
        const resp = await fetch("/api/generate-and-process", {
          method: "POST",
          body: formData
        });
        const json = await resp.json();

        if (json.code === 0 && json.data) {
          fileNameDisplay.textContent = "✨ 来自 ChatGPT Plus (Images 2.5) 原生出图并完成切割";
          displayResults(json.data);
        } else {
          alert("AI 出图或切片失败: " + (json.detail || json.message || "未知错误"));
        }
      } catch (err) {
        alert("网络请求异常: " + err.message);
      } finally {
        btnAIGenerate.disabled = false;
        btnAIGenerate.innerText = origText;
        if (aiLoadingStatus) aiLoadingStatus.style.display = "none";
      }
    });
  }

  // 渲染结果
  function displayResults(data) {
    resultCard.style.display = "block";
    resultCard.scrollIntoView({ behavior: "smooth" });

    // 动图预览带时间戳
    const timestamp = new Date().getTime();
    gifImage.src = `${data.gif_url}?t=${timestamp}`;

    // 指标信息
    statFrames.textContent = `${data.stats.frame_count} 帧`;
    statSize.textContent = `${data.stats.file_size_kb} KB`;
    statDuration.textContent = `${data.stats.duration_per_frame_ms} ms / 帧`;

    btnDownloadGif.href = data.gif_url;
    btnDownloadZip.href = data.zip_url;

    // 16 帧画廊
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

    // 激活工作流步骤高亮
    document.querySelectorAll(".step-item").forEach(s => s.classList.add("active"));
  }
});
