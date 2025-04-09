// 等待DOM加载完成
document.addEventListener('DOMContentLoaded', function() {
    // 表单提交前进行验证
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(event) {
            const textarea = form.querySelector('textarea');
            if (textarea && textarea.value.trim().length < 10) {
                event.preventDefault();
                alert('请提供更详细的描述，至少10个字符。');
                textarea.focus();
            }
        });
    });
    
    // 如果页面上有图片，添加加载指示器
    const storyImages = document.querySelectorAll('.story-image img');
    storyImages.forEach(img => {
        // 添加加载中的状态
        img.style.opacity = '0.5';
        img.parentElement.classList.add('loading');
        
        // 图片加载完成后移除加载状态
        img.addEventListener('load', function() {
            img.style.opacity = '1';
            img.parentElement.classList.remove('loading');
        });
        
        // 图片加载失败处理
        img.addEventListener('error', function() {
            img.style.display = 'none';
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-image';
            errorDiv.textContent = '图片加载失败';
            img.parentElement.appendChild(errorDiv);
        });
    });
}); 