#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复 upload.js 中 DOM ID 引用与 HTML 不一致的问题"""
import os

# 创建修复后的 upload.js
JS_CONTENT = r'''/**
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
        el.addEventListener('input', function() {
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
    var submitBtn = document.getElementById('submit-btn');
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
    var countEl = document.getElementById('file-count');
    if (countEl) {
      countEl.textContent = selectedFiles.length > 0 
        ? '已选择 ' + selectedFiles.length + ' 张照片' 
        : '未选择';
    }
  }

  /**
   * 显示预览
   */
  function showPreview() {
    var previewArea = document.getElementById('preview-area');
    var previewGrid = document.getElementById('preview-grid');
    var previewCount = document.getElementById('preview-count');
    
    if (!previewArea || !previewGrid) return;
    
    // 显示预览区域
    previewArea.classList.remove('hidden');
    
    // 更新计数
    if (previewCount) {
      previewCount.textContent = selectedFiles.length + ' 张照片';
    }
    
    // 生成预览
    previewGrid.innerHTML = '';
    
    selectedFiles.forEach(function(file, index) {
      var reader = new FileReader();
      reader.onload = function(e) {
        var item = document.createElement('div');
        item.className = 'preview-item';
        
        var img = document.createElement('img');
        img.src = e.target.result;
        img.alt = file.name;
        
        var removeBtn = document.createElement('div');
        removeBtn.className = 'remove-btn';
        removeBtn.textContent = '\u00d7';
        removeBtn.setAttribute('data-index', index);
        removeBtn.addEventListener('click', function() {
          removeFile(parseInt(this.getAttribute('data-index')));
        });
        
        item.appendChild(img);
        item.appendChild(removeBtn);
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
    if (selectedFiles.length > 0) {
      showPreview();
    } else {
      hidePreview();
    }
    validateForm();
  }

  /**
   * 隐藏预览
   */
  function hidePreview() {
    var previewArea = document.getElementById('preview-area');
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
    
    // 准备上传数据
    var formData = new FormData();
    formData.append('owner', uploadForm.owner);
    formData.append('date', uploadForm.date);
    formData.append('event', uploadForm.event);
    formData.append('persons', uploadForm.persons);
    formData.append('location', uploadForm.location);
    
    selectedFiles.forEach(function(file) {
      formData.append('photos', file, file.name);
    });
    
    // 显示进度
    showProgress();
    
    // 执行上传
    uploadToServer(formData);
  }

  /**
   * 显示进度
   */
  function showProgress() {
    var progressArea = document.getElementById('progress-area');
    var submitBtn = document.getElementById('submit-btn');
    
    if (progressArea) {
      progressArea.classList.remove('hidden');
    }
    if (submitBtn) {
      submitBtn.disabled = true;
    }
    updateProgress(0, '准备上传...');
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
        try {
          var result = JSON.parse(xhr.responseText);
          showSuccess(result);
        } catch(e) {
          showError('服务器返回异常');
        }
      } else {
        showError('上传失败：' + xhr.statusText);
      }
    });
    
    xhr.addEventListener('error', function() {
      showError('网络错误，请重试');
    });
    
    xhr.addEventListener('timeout', function() {
      showError('上传超时，请重试');
    });
    
    xhr.timeout = 300000; // 5分钟超时
    xhr.open('POST', '/api/upload');
    xhr.send(formData);
  }

  /**
   * 显示成功
   */
  function showSuccess(result) {
    var progressArea = document.getElementById('progress-area');
    var resultArea = document.getElementById('result-area');
    var resultIcon = document.getElementById('result-icon');
    var resultTitle = document.getElementById('result-title');
    var resultInfo = document.getElementById('result-info');
    
    if (progressArea) progressArea.classList.add('hidden');
    if (resultArea) resultArea.classList.remove('hidden');
    
    if (resultIcon) {
      resultIcon.className = 'result-icon success';
      resultIcon.textContent = '\u2713';
    }
    if (resultTitle) {
      resultTitle.textContent = '上传成功';
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
    var progressArea = document.getElementById('progress-area');
    var resultArea = document.getElementById('result-area');
    var resultIcon = document.getElementById('result-icon');
    var resultTitle = document.getElementById('result-title');
    var resultInfo = document.getElementById('result-info');
    
    if (progressArea) progressArea.classList.add('hidden');
    if (resultArea) resultArea.classList.remove('hidden');
    
    if (resultIcon) {
      resultIcon.className = 'result-icon error';
      resultIcon.textContent = '\u2717';
    }
    if (resultTitle) {
      resultTitle.textContent = '上传失败';
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
    var ownerEl = document.getElementById('upload-owner');
    var dateEl = document.getElementById('upload-date');
    var eventEl = document.getElementById('upload-event');
    var personsEl = document.getElementById('upload-persons');
    var locationEl = document.getElementById('upload-location');
    
    if (ownerEl) ownerEl.value = '';
    if (dateEl) dateEl.value = new Date().toISOString().split('T')[0];
    if (eventEl) eventEl.value = '';
    if (personsEl) personsEl.value = '';
    if (locationEl) locationEl.value = '';
    
    // 重置状态
    uploadForm = { owner: '', date: '', event: '', persons: '', location: '' };
    
    // 清空文件
    clearFiles();
    
    // 隐藏结果和进度
    var resultArea = document.getElementById('result-area');
    if (resultArea) resultArea.classList.add('hidden');
    
    var progressArea = document.getElementById('progress-area');
    if (progressArea) progressArea.classList.add('hidden');
    
    // 重置进度条
    var progressFill = document.getElementById('progress-fill');
    if (progressFill) progressFill.style.width = '0%';
    
    // 启用按钮
    var submitBtn = document.getElementById('submit-btn');
    if (submitBtn) submitBtn.disabled = true;
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
'''

JS_PATH = r'G:\AI\PZ\engine\upload.js'
with open(JS_PATH, 'w', encoding='utf-8') as f:
    f.write(JS_CONTENT)

print('✓ upload.js 已修复（ID引用与HTML一致）')
