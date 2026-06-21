/**
 * 尚唯云册 - 照片上传功能
 * 手机端上传页面逻辑
 */

(function() {
  'use strict';

  // 状态
  var selectedFiles = [];
  var uploadForm = {
    owner: '',
    date: '',
    event: '',
    persons: '',
    location: ''
  };

  /**
   * 初始化上传页面
   */
  function initUploadPage() {
    console.log('[Upload] 初始化上传页面');
    
    // 绑定文件选择事件
    var fileInput = document.getElementById('upload-files');
    if (fileInput) {
      fileInput.addEventListener('change', handleFileSelect);
    }
    
    // 绑定表单变化事件
    bindFormEvents();
    
    // 设置默认日期为今天
    var dateInput = document.getElementById('upload-date');
    if (dateInput && !dateInput.value) {
      dateInput.value = new Date().toISOString().split('T')[0];
    }
  }

  /**
   * 绑定表单事件
   */
  function bindFormEvents() {
    var fields = ['upload-owner', 'upload-date', 'upload-event', 'upload-persons', 'upload-location'];
    
    fields.forEach(function(id) {
      var el = document.getElementById(id);
      if (el) {
        el.addEventListener('change', function() {
          updateFormState();
          validateForm();
        });
      }
    });
  }

  /**
   * 更新表单状态
   */
  function updateFormState() {
    uploadForm.owner = document.getElementById('upload-owner').value;
    uploadForm.date = document.getElementById('upload-date').value;
    uploadForm.event = document.getElementById('upload-event').value;
    uploadForm.persons = document.getElementById('upload-persons').value;
    uploadForm.location = document.getElementById('upload-location').value;
  }

  /**
   * 验证表单
   */
  function validateForm() {
    var isValid = uploadForm.owner && uploadForm.event && selectedFiles.length > 0;
    var submitBtn = document.getElementById('upload-submit');
    if (submitBtn) {
      submitBtn.disabled = !isValid;
    }
    return isValid;
  }

  /**
   * 处理文件选择
   */
  function handleFileSelect(e) {
    var files = Array.from(e.target.files);
    
    if (files.length === 0) return;
    
    // 添加到已选文件
    selectedFiles = selectedFiles.concat(files);
    
    // 更新UI
    updateFileCount();
    showPreview();
    validateForm();
  }

  /**
   * 更新文件计数
   */
  function updateFileCount() {
    var countEl = document.getElementById('upload-file-count');
    if (countEl) {
      countEl.textContent = selectedFiles.length > 0 
        ? '已选择 ' + selectedFiles.length + ' 张照片' 
        : '未选择文件';
    }
  }

  /**
   * 显示预览
   */
  function showPreview() {
    var previewArea = document.getElementById('upload-preview');
    var previewGrid = document.getElementById('preview-grid');
    var previewCount = document.getElementById('preview-count');
    
    if (!previewArea || !previewGrid) return;
    
    // 显示预览区域
    previewArea.classList.remove('hidden');
    
    // 更新计数
    if (previewCount) {
      previewCount.textContent = selectedFiles.length;
    }
    
    // 生成预览
    previewGrid.innerHTML = '';
    
    selectedFiles.forEach(function(file, index) {
      var reader = new FileReader();
      reader.onload = function(e) {
        var item = document.createElement('div');
        item.className = 'preview-item';
        item.innerHTML = 
          '<img src="' + e.target.result + '" alt="">' +
          '<div class="remove-btn" onclick="removeFile(' + index + ')">×</div>';
        previewGrid.appendChild(item);
      };
      reader.readAsDataURL(file);
    });
  }

  /**
   * 移除文件
   */
  function removeFile(index) {
    selectedFiles.splice(index, 1);
    updateFileCount();
    showPreview();
    validateForm();
    
    if (selectedFiles.length === 0) {
      hidePreview();
    }
  }

  /**
   * 隐藏预览
   */
  function hidePreview() {
    var previewArea = document.getElementById('upload-preview');
    if (previewArea) {
      previewArea.classList.add('hidden');
    }
  }

  /**
   * 清空文件
   */
  function clearFiles() {
    selectedFiles = [];
    var fileInput = document.getElementById('upload-files');
    if (fileInput) {
      fileInput.value = '';
    }
    updateFileCount();
    hidePreview();
    validateForm();
  }

  /**
   * 提交上传
   */
  function submitUpload() {
    if (!validateForm()) {
      alert('请填写必要信息并选择照片');
      return;
    }
    
    // 生成文件夹名称
    var folderName = generateFolderName();
    
    // 准备上传数据
    var formData = new FormData();
    formData.append('folder', folderName);
    formData.append('owner', uploadForm.owner);
    formData.append('date', uploadForm.date);
    formData.append('event', uploadForm.event);
    formData.append('persons', uploadForm.persons);
    formData.append('location', uploadForm.location);
    
    selectedFiles.forEach(function(file, index) {
      formData.append('photos', file, file.name);
    });
    
    // 显示进度
    showProgress();
    
    // 执行上传
    uploadToServer(formData);
  }

  /**
   * 生成文件夹名称
   * 格式：[归属]-[日期]-[事件]-[人物/地点]
   */
  function generateFolderName() {
    var parts = [];
    
    // 归属
    if (uploadForm.owner) {
      parts.push(uploadForm.owner);
    }
    
    // 日期（格式化）
    if (uploadForm.date) {
      var dateStr = uploadForm.date.replace(/-/g, '');
      // 补全日期
      if (dateStr.length === 4) {
        dateStr += '0000'; // 只有年份
      } else if (dateStr.length === 6) {
        dateStr += '00'; // 只有年月
      }
      parts.push(dateStr);
    } else {
      parts.push('00000000');
    }
    
    // 事件
    if (uploadForm.event) {
      parts.push(uploadForm.event);
    }
    
    // 人物或地点
    if (uploadForm.persons) {
      parts.push(uploadForm.persons.replace(/\//g, '-'));
    } else if (uploadForm.location) {
      parts.push(uploadForm.location);
    }
    
    return parts.join('-');
  }

  /**
   * 显示进度
   */
  function showProgress() {
    var progressArea = document.getElementById('upload-progress');
    var submitBtn = document.getElementById('upload-submit');
    
    if (progressArea) {
      progressArea.classList.remove('hidden');
    }
    if (submitBtn) {
      submitBtn.disabled = true;
    }
  }

  /**
   * 更新进度
   */
  function updateProgress(percent, text) {
    var progressFill = document.getElementById('progress-fill');
    var progressText = document.getElementById('progress-text');
    
    if (progressFill) {
      progressFill.style.width = percent + '%';
    }
    if (progressText) {
      progressText.textContent = text || '';
    }
  }

  /**
   * 上传到服务器
   */
  function uploadToServer(formData) {
    var xhr = new XMLHttpRequest();
    
    xhr.upload.addEventListener('progress', function(e) {
      if (e.lengthComputable) {
        var percent = Math.round((e.loaded / e.total) * 100);
        updateProgress(percent, '上传中 ' + percent + '%');
      }
    });
    
    xhr.addEventListener('load', function() {
      if (xhr.status === 200) {
        var result = JSON.parse(xhr.responseText);
        showSuccess(result);
      } else {
        showError('上传失败：' + xhr.statusText);
      }
    });
    
    xhr.addEventListener('error', function() {
      showError('网络错误，请重试');
    });
    
    xhr.open('POST', '/api/upload');
    xhr.send(formData);
  }

  /**
   * 显示成功
   */
  function showSuccess(result) {
    var progressArea = document.getElementById('upload-progress');
    var resultArea = document.getElementById('upload-result');
    var resultInfo = document.getElementById('result-info');
    
    if (progressArea) {
      progressArea.classList.add('hidden');
    }
    if (resultArea) {
      resultArea.classList.remove('hidden');
      var icon = resultArea.querySelector('.result-icon');
      if (icon) {
        icon.className = 'result-icon success';
        icon.textContent = '✓';
      }
    }
    if (resultInfo) {
      resultInfo.innerHTML = 
        '上传照片：<strong>' + result.count + '</strong> 张<br>' +
        '保存位置：<strong>' + result.folder + '</strong><br>' +
        '网站已自动更新';
    }
  }

  /**
   * 显示错误
   */
  function showError(message) {
    var progressArea = document.getElementById('upload-progress');
    var resultArea = document.getElementById('upload-result');
    var resultInfo = document.getElementById('result-info');
    
    if (progressArea) {
      progressArea.classList.add('hidden');
    }
    if (resultArea) {
      resultArea.classList.remove('hidden');
      var icon = resultArea.querySelector('.result-icon');
      if (icon) {
        icon.className = 'result-icon error';
        icon.textContent = '✗';
      }
      var title = resultArea.querySelector('.result-title');
      if (title) {
        title.textContent = '上传失败';
      }
    }
    if (resultInfo) {
      resultInfo.textContent = message;
    }
  }

  /**
   * 重置上传
   */
  function resetUpload() {
    // 清空表单
    document.getElementById('upload-owner').value = '';
    document.getElementById('upload-date').value = new Date().toISOString().split('T')[0];
    document.getElementById('upload-event').value = '';
    document.getElementById('upload-persons').value = '';
    document.getElementById('upload-location').value = '';
    
    // 清空文件
    clearFiles();
    
    // 隐藏结果
    var resultArea = document.getElementById('upload-result');
    if (resultArea) {
      resultArea.classList.add('hidden');
    }
    
    // 启用按钮
    var submitBtn = document.getElementById('upload-submit');
    if (submitBtn) {
      submitBtn.disabled = true;
    }
  }

  // 导出全局函数
  window.removeFile = removeFile;
  window.clearFiles = clearFiles;
  window.submitUpload = submitUpload;
  window.resetUpload = resetUpload;

  // DOM加载后初始化
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initUploadPage);
  } else {
    initUploadPage();
  }

})();
