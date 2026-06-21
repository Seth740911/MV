/**
 * 尚唯云册 - 懒加载引擎
 * 按需加载图片，提升首屏性能
 */

(function() {
  'use strict';

  // 配置
  var CONFIG = {
    // 首屏加载数量
    initialLoad: {
      pc: 20,
      mobile: 15,
      tv: 10
    },
    // 滚动加载数量
    scrollLoad: {
      pc: 50,
      mobile: 30,
      tv: 20
    },
    // 预加载距离（px）
    preloadDistance: 500,
    // 图片加载延迟（ms）
    loadDelay: 100
  };

  // 设备检测
  function getDeviceType() {
    if (typeof tvApp !== 'undefined') return 'tv';
    if (window.innerWidth <= 800) return 'mobile';
    return 'pc';
  }

  // 懒加载器
  function LazyLoader() {
    this.device = getDeviceType();
    this.loadedCount = 0;
    this.isLoading = false;
    this.observer = null;
    this.images = [];
  }

  LazyLoader.prototype = {
    init: function() {
      var self = this;
      
      // 获取所有需要懒加载的图片
      this.images = Array.from(document.querySelectorAll('img[data-src]'));
      
      if (this.images.length === 0) return;
      
      // 首屏加载
      var initialCount = CONFIG.initialLoad[this.device];
      this.loadNext(initialCount);
      
      // 监听滚动事件
      this.setupScrollListener();
      
      // 使用 IntersectionObserver（如果支持）
      if ('IntersectionObserver' in window) {
        this.setupIntersectionObserver();
      }
      
      console.log('[LazyLoader] 初始化完成，设备:', this.device, '图片总数:', this.images.length);
    },

    setupScrollListener: function() {
      var self = this;
      var scrollTimer = null;
      
      window.addEventListener('scroll', function() {
        if (scrollTimer) clearTimeout(scrollTimer);
        
        scrollTimer = setTimeout(function() {
          self.checkScroll();
        }, 100);
      });
    },

    checkScroll: function() {
      var scrollBottom = window.innerHeight + window.scrollY;
      var docHeight = document.documentElement.scrollHeight;
      
      // 距离底部 preloadDistance 时加载更多
      if (scrollBottom >= docHeight - CONFIG.preloadDistance) {
        this.loadMore();
      }
    },

    setupIntersectionObserver: function() {
      var self = this;
      
      this.observer = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
          if (entry.isIntersecting) {
            var img = entry.target;
            self.loadImage(img);
            self.observer.unobserve(img);
          }
        });
      }, {
        rootMargin: CONFIG.preloadDistance + 'px'
      });
      
      // 观察所有未加载的图片
      this.images.forEach(function(img) {
        if (!img.src || img.src === '') {
          self.observer.observe(img);
        }
      });
    },

    loadMore: function() {
      if (this.isLoading) return;
      
      var count = CONFIG.scrollLoad[this.device];
      this.loadNext(count);
    },

    loadNext: function(count) {
      var self = this;
      
      if (this.loadedCount >= this.images.length) return;
      
      this.isLoading = true;
      
      var end = Math.min(this.loadedCount + count, this.images.length);
      var loaded = 0;
      
      for (var i = this.loadedCount; i < end; i++) {
        (function(index) {
          setTimeout(function() {
            self.loadImage(self.images[index]);
            loaded++;
            
            if (loaded === end - self.loadedCount) {
              self.loadedCount = end;
              self.isLoading = false;
              
              // 触发自定义事件
              window.dispatchEvent(new CustomEvent('lazyload:progress', {
                detail: {
                  loaded: self.loadedCount,
                  total: self.images.length
                }
              }));
            }
          }, CONFIG.loadDelay * (index - self.loadedCount));
        })(i);
      }
    },

    loadImage: function(img) {
      if (!img || img.src) return;
      
      var src = img.getAttribute('data-src');
      if (!src) return;
      
      // 创建临时图片预加载
      var tempImg = new Image();
      
      tempImg.onload = function() {
        img.src = src;
        img.classList.add('loaded');
        
        // 移除 data-src 属性
        img.removeAttribute('data-src');
        
        // 触发加载完成事件
        img.dispatchEvent(new CustomEvent('lazyload:loaded'));
      };
      
      tempImg.onerror = function() {
        console.error('[LazyLoader] 图片加载失败:', src);
        img.classList.add('load-error');
      };
      
      tempImg.src = src;
    },

    // 强制加载所有图片
    loadAll: function() {
      var self = this;
      
      this.images.forEach(function(img) {
        if (!img.src || img.src === '') {
          self.loadImage(img);
        }
      });
      
      this.loadedCount = this.images.length;
    },

    // 获取加载进度
    getProgress: function() {
      return {
        loaded: this.loadedCount,
        total: this.images.length,
        percentage: Math.round((this.loadedCount / this.images.length) * 100)
      };
    }
  };

  // 全局懒加载器实例
  window.lazyLoader = new LazyLoader();

  // DOM 加载完成后初始化
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      window.lazyLoader.init();
    });
  } else {
    window.lazyLoader.init();
  }

  // 导出配置
  window.LazyLoaderConfig = CONFIG;

})();
