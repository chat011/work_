
// Global variable to store options data
let optionsData = {
    colors: [],
    sizes: [],
    materials: [],
    categories: []
};

// Function to fetch options data from API
async function fetchOptionsData() {
    try {
        // In a real implementation, you would fetch from the actual API
        // For demo purposes, we'll use the sample data you provided
        const sampleData = {
            "status": true,
            "message": "Option data & categories retrieved successfully",
            "data": {
                "colorOptions": [{
                    "_id": "601a67fd4e966936d4f475d4",
                    "option_name": "Color",
                    "option_values": [
                        { "status": "1", "_id": "6509a8b877379f22b05e17a1", "option_value_name": "Beige", "sort_order": 21, "color_code": "#f5f5dc" },
                        { "status": "1", "_id": "6509a8b877379f22b05e1791", "option_value_name": "Black", "sort_order": 5, "color_code": "#000000" },
                        { "status": "1", "_id": "64ca7b8880532780f4a1dddb", "option_value_name": "Blue", "sort_order": 1, "color_code": "#0000ff" },
                        { "status": "1", "_id": "6509a8b877379f22b05e17df", "option_value_name": "Bronze", "sort_order": 48, "color_code": "#aa6c39" },
                        { "status": "1", "_id": "6509a8b877379f22b05e17a9", "option_value_name": "Brown", "sort_order": 27, "color_code": "#a52a2a" }
                    ]
                }],
                "sizeOptions": [{
                    "_id": "601a68b54e966936d4f475db",
                    "option_name": "Size",
                    "option_values": [
                        { "status": "1", "_id": "6554e4b70d9254bece34f663", "option_value_name": "Free size", "sort_order": 1, "color_code": "" },
                        { "status": "1", "_id": "60547418e1680a3111d00735", "option_value_name": "XS", "sort_order": 2, "color_code": "" },
                        { "status": "1", "_id": "60547418e1680a3111d00736", "option_value_name": "S", "sort_order": 3, "color_code": "" },
                        { "status": "1", "_id": "60547418e1680a3111d00737", "option_value_name": "M", "sort_order": 4, "color_code": "" },
                        { "status": "1", "_id": "60547418e1680a3111d00738", "option_value_name": "L", "sort_order": 5, "color_code": "" }
                    ]
                }],
                "materialOptions": [{
                    "_id": "601a6a544e966936d4f475e2",
                    "option_name": "Materials",
                    "option_values": [
                        { "status": "1", "_id": "615ecc7ece2599c2b42e9619", "option_value_name": "Cotton", "sort_order": 1 },
                        { "status": "1", "_id": "615ecc7ece2599c2b42e961a", "option_value_name": "Rayon", "sort_order": 2 },
                        { "status": "1", "_id": "615ecc7ece2599c2b42e961b", "option_value_name": "Net", "sort_order": 3 },
                        { "status": "1", "_id": "615ecc7ece2599c2b42e961c", "option_value_name": "Twill", "sort_order": 4 },
                        { "status": "1", "_id": "615ecc7ece2599c2b42e961d", "option_value_name": "Neon", "sort_order": 5 }
                    ]
                }],
                "allCategories": [
                    { "_id": "601a4e5cc63f8b34c1b5f21e", "status": "1", "category_name": "Bottom Wear > Causal Trousers", "parent_id": "601a4c9cc63f8b34c1b5f1fd" },
                    { "_id": "62d6d1c1c62feb75a49e495d", "status": "1", "category_name": "Bottom Wear > Formal Trousers", "parent_id": "601a4c9cc63f8b34c1b5f1fd" },
                    { "_id": "62d6d13ec62feb75a49e495b", "status": "1", "category_name": "Bottom Wear > Jeans", "parent_id": "601a4c9cc63f8b34c1b5f1fd" },
                    { "_id": "62d6d200c62feb75a49e495e", "status": "1", "category_name": "Bottom Wear > Shorts", "parent_id": "601a4c9cc63f8b34c1b5f1fd" },
                    { "_id": "62d6d226c62feb75a49e495f", "status": "1", "category_name": "Bottom Wear > Track Pants & Joggers", "parent_id": "601a4c9cc63f8b34c1b5f1fd" }
                ]
            }
        };

        if (sampleData.status) {
            optionsData = {
                colors: sampleData.data.colorOptions[0].option_values,
                sizes: sampleData.data.sizeOptions[0].option_values,
                materials: sampleData.data.materialOptions[0].option_values,
                categories: sampleData.data.allCategories
            };

            // Sort options by sort_order where applicable
            optionsData.colors.sort((a, b) => a.sort_order - b.sort_order);
            optionsData.sizes.sort((a, b) => a.sort_order - b.sort_order);
            optionsData.materials.sort((a, b) => a.sort_order - b.sort_order);

            return true;
        } else {
            console.error('Failed to fetch options data:', sampleData.message);
            return false;
        }
    } catch (error) {
        console.error('Error fetching options data:', error);
        return false;
    }
}

class ProductEditor {
    constructor() {
        this.products = [];
        this.originalProducts = [];
        this.modifiedRows = new Set();
    }

    async init() {
        // Load options data first
        await fetchOptionsData();
        await this.loadProducts();
        this.renderTable();
        this.updateStats();
    }

    async loadProducts() {
        // Check if task_id is provided in URL
        const urlParams = new URLSearchParams(window.location.search);
        const taskId = urlParams.get('task_id');

        if (taskId) {
            await this.loadProductsFromTask(taskId);
        } else {
            const storedProducts = localStorage.getItem('selectedProducts');
            if (storedProducts) {
                this.products = JSON.parse(storedProducts);
                this.originalProducts = JSON.parse(JSON.stringify(this.products));
            } else {
                // Demo data for testing
                this.products = [
                    {
                        product_name: "Patachio Princess Gown",
                        price: 8999,
                        discounted_price: 0,
                        availability: "in-stock",
                        description: "Introducing our 'Patachio Princess Gown', a captivating blend of elegance and playfulness.",
                        sizes: ["S", "M", "L"],
                        colors: ["Purple", "Lilac"],
                        material: "Satin",
                        categories: ["Dresses", "Women", "Formal"],
                        product_images: [],
                        premium: false
                    },
                    {
                        product_name: "Lilac Princess Purple Ball Gown",
                        price: 10999,
                        discounted_price: 0,
                        availability: "in-stock",
                        description: "Introducing 'Lilac Princess,' a stunning purple ball gown that embodies elegance",
                        sizes: ["M", "L", "XL"],
                        colors: ["Purple", "Lavender"],
                        material: "Chiffon",
                        categories: ["Dresses", "Women", "Formal"],
                        product_images: [],
                        premium: true
                    }
                ];
                this.originalProducts = JSON.parse(JSON.stringify(this.products));
            }
        }
    }

    async loadProductsFromTask(taskId) {
        try {
            // This would be your actual API call
            // For demo, we'll use the sample data above
            const response = { ok: true };
            const data = {
                success: true,
                products: this.products,
                scraper_type: "fashion",
                is_fixed_version: true
            };

            if (response.ok && data.success) {
                this.products = data.products;
                this.originalProducts = JSON.parse(JSON.stringify(this.products));

                // Show task info
                document.getElementById('currentTaskId').textContent = taskId;
                const scraperTypeText = data.scraper_type.toUpperCase() + (data.is_fixed_version ? ' (FIXED)' : ' (ORIGINAL)');
                document.getElementById('scraperType').textContent = scraperTypeText;
                document.getElementById('taskInfo').style.display = 'block';

                const versionText = data.is_fixed_version ? 'FIXED version with optimized image URLs' : 'original version';
                this.showNotification(`Loaded ${data.products.length} products from task ${taskId} (${versionText})`, 'success');
            } else {
                throw new Error(data.message || 'Failed to load products from task');
            }
        } catch (error) {
            console.error('Error loading products from task:', error);
            this.showNotification(`Failed to load products from task: ${error.message}`, 'error');
        }
    }

    renderTable() {
        const tbody = document.getElementById('productsTableBody');
        tbody.innerHTML = '';

        this.products.forEach((product, index) => {
            const row = this.createProductRow(product, index);
            tbody.appendChild(row);
        });

        // Initialize dropdowns after rendering

    }
    

    createProductRow(product, index) {
        const row = document.createElement('tr');
        row.dataset.index = index;

        const images = product.product_images || [];
        const sizesText = Array.isArray(product.sizes) ? product.sizes.join(', ') : (product.sizes || '');
        const colorsText = Array.isArray(product.colors) ? product.colors.join(', ') : (product.colors || '');
        const categoriesText = Array.isArray(product.metadata?.categories) ? product.metadata.categories.join(', ') : (product.categories ? (Array.isArray(product.categories) ? product.categories.join(', ') : product.categories) : '');
        const availability = product.availability || 'in-stock';
        const allImagesText = images.join('\n');

        // Determine if product is premium (price >= 25000)
        const isPremium = (product.price || 0) >= 25000;

        // Create image preview HTML
        const imagePreviewsHTML = images.slice(0, 4).map((img, imgIndex) => {
            return `
                        <div class="image-wrapper">
                            <img src="${img}" alt="Product ${imgIndex + 1}" class="product-image-preview" 
                                 onclick="productEditor.openImagePreview('${img}')"
                                 onerror="this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDUiIGhlaWdodD0iNDUiIHZpZXdCb3g9IjAgMCA0NSA0NSIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHJlY3Qgd2lkdGg9IjQ1IiBoZWlnaHQ9IjQ1IiBmaWxsPSIjRjFGNUY5Ii8+CjxwYXRoIGQ9Ik0yMi41IDIyLjVDMjIuNSAyMC4wMTQ3IDI0LjUxNDcgMTggMjcgMThDMjkuNDg1MyAxOCAzMS41IDIwLjAxNDcgMzEuNSAyMi41QzMxLjUgMjQuOTg1MyAyOS40ODUzIDI3IDI3IDI3QzI0LjUxNDcgMjcgMjIuNSAyNC45ODUzIDIyLjUgMjIuNVoiIGZpbGw9IiNDQkQ1RTEiLz4KPHBhdGggZD0iTTE4IDI3SDI3TDI1LjUgMjkuMjVIMjAuMjVMMTggMjdaIiBmaWxsPSIjQ0JENUUxIi8+Cjwvc3ZnPgo='">
                            <button class="image-remove-btn" onclick="event.stopPropagation(); productEditor.removeImage(${index}, ${imgIndex})" title="Remove image">
                                <i class="fas fa-times"></i>
                            </button>
                            <div class="image-status" title="Availability unknown"></div>
                        </div>
                    `;
        }).join('');

        // Add "Add Image" button if we have space
        const addImageButton = images.length < 4 ?
            `<div class="add-image-btn" onclick="productEditor.addImage(${index})" title="Add image URL">
                        <i class="fas fa-plus"></i>
                    </div>` : '';

        const moreImagesIndicator = images.length > 4 ? `<div style="font-size: 0.7rem; color: var(--text-secondary); margin-top: 4px; cursor: pointer;" onclick="productEditor.showAllImages(${index})">+${images.length - 4} more</div>` : '';

        const finalImageHTML = imagePreviewsHTML + addImageButton;

        row.innerHTML = `
                    <td>
                        <input type="checkbox" class="row-checkbox" onchange="productEditor.updateStats()">
                    </td>
                    <td class="product-image-cell">
                        <div class="image-container">
                            ${finalImageHTML}
                        </div>
                        ${moreImagesIndicator}
                    </td>
                    <td>
                        <div class="image-sizes-dropdown">
                            <button class="image-sizes-toggle" onclick="toggleImageSizes(this)">
                                <span class="image-sizes-count">${product.image_sizes ? product.image_sizes.length : 0}</span> sizes
                                <i class="fas fa-chevron-down"></i>
                            </button>
                            <div class="image-sizes-dropdown-content">
                                ${product.image_sizes && product.image_sizes.length > 0 ?
                product.image_sizes.map(s => `<div class="image-size-item">${s.width}x${s.height}</div>`).join('') :
                '<div class="image-size-item">No size data</div>'
            }
                            </div>
                        </div>
                    </td>
                    <td>
                        <textarea class="editable-cell name-input" 
                                  onchange="productEditor.markModified(${index})" 
                                  oninput="productEditor.autoResizeTextarea(this)"
                                  placeholder="Product name">${product.product_name || ''}</textarea>
                    </td>
                    <td>
                        <input type="number" class="editable-cell price-input" onchange="productEditor.updatePremiumStatus(${index}); productEditor.markModified(${index})" 
                               placeholder="0.00" step="0.01" value="${product.price || ''}">
                    </td>
                    <td>
                        <input type="number" class="editable-cell price-input" onchange="productEditor.markModified(${index})" 
                               placeholder="0.00" step="0.01" value="${product.discounted_price || ''}" title="Discounted Price (Optional)">
                    </td>
                    <td>
                        <select class="availability-select ${availability}" onchange="productEditor.markModified(${index}); productEditor.updateAvailabilityStyle(this)">
                            <option value="in-stock" ${availability === 'in-stock' ? 'selected' : ''}>In Stock</option>
                            <option value="out-of-stock" ${availability === 'out-of-stock' ? 'selected' : ''}>Out of Stock</option>
                            <option value="limited" ${availability === 'limited' ? 'selected' : ''}>Limited</option>
                            <option value="preorder" ${availability === 'preorder' ? 'selected' : ''}>Pre-order</option>
                        </select>
                    </td>
                    <td>
                        <textarea class="editable-cell description-input" 
                                  onchange="productEditor.markModified(${index})" 
                                  oninput="productEditor.autoResizeTextarea(this)"
                                  placeholder="Product description">${product.description || ''}</textarea>
                    </td>
                    <td>
                        ${createDropdown('sizes', index, true)}
                    </td>
                    <td>
                        ${createDropdown('colors', index, true)}
                    </td>
                    <td>
                        ${createDropdown('materials', index, false)}
                    </td>
                    <td>
                        ${createDropdown('categories', index, false)}
                    </td>
                    <td>
                        <div class="row-actions">
                            <button class="row-btn view tooltip" onclick="productEditor.openProductUrl(${index})" data-tooltip="View source product page" ${!(product.url || product.source_url) ? 'disabled' : ''}>
                                <i class="fas fa-external-link-alt"></i>
                            </button>
                            <button class="row-btn duplicate tooltip" onclick="productEditor.duplicateRow(${index})" data-tooltip="Duplicate this product">
                                <i class="fas fa-copy"></i>
                            </button>
                            <button class="row-btn delete tooltip" onclick="productEditor.deleteRow(${index})" data-tooltip="Delete this product">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </td>
                    <td>
                        <label class="premium-toggle">
                            <input type="checkbox" ${isPremium ? 'checked' : ''} onchange="productEditor.markModified(${index})">
                            <span class="toggle-slider"></span>
                        </label>
                    </td>
                `;

        return row;
    }

    updateToggleText(toggle, selectedContainer, multiple) {
        const selectedCount = selectedContainer.querySelectorAll('.selected-tag').length;
        if (multiple) {
            toggle.querySelector('.selected-text').textContent = selectedCount > 0 ? `${selectedCount} selected` : 'Select options';
        } else {
            const selectedTag = selectedContainer.querySelector('.selected-tag');
            toggle.querySelector('.selected-text').textContent = selectedTag ? selectedTag.textContent.replace('×', '') : 'Select option';
        }
    }

    getCurrentValues(field, index) {
        const product = this.products[index];
        let currentValues = [];

        switch (field) {
            case 'sizes':
                currentValues = Array.isArray(product.sizes) ? [...product.sizes] : (product.sizes ? [product.sizes] : []);
                break;
            case 'colors':
                currentValues = Array.isArray(product.colors) ? [...product.colors] : (product.colors ? [product.colors] : []);
                break;
            case 'materials':
                currentValues = product.material ? [product.material] : [];
                break;
            case 'categories':
                currentValues = Array.isArray(product.categories) ? [...product.categories] : (product.categories ? [product.categories] : []);
                break;
        }

        return currentValues;
    }

    updateProductValue(field, value, index) {
        const product = this.products[index];

        switch (field) {
            case 'sizes':
                product.sizes = value;
                break;
            case 'colors':
                product.colors = value;
                break;
            case 'materials':
                product.material = value.length > 0 ? value[0] : '';
                break;
            case 'categories':
                product.categories = value;
                break;
        }

        // Mark the product as modified
        this.markModified(index);
    }

    updatePremiumStatus(index) {
        const priceInput = document.querySelector(`tr[data-index="${index}"] .price-input`);
        const premiumToggle = document.querySelector(`tr[data-index="${index}"] .premium-toggle input`);

        if (priceInput && premiumToggle) {
            const price = parseFloat(priceInput.value) || 0;
            premiumToggle.checked = price >= 25000;
        }

        this.updateStats();
    }

    markModified(index) {
        this.modifiedRows.add(index);
        const row = document.querySelector(`tr[data-index="${index}"]`);
        if (row) {
            row.querySelectorAll('.editable-cell, .availability-select').forEach(cell => {
                cell.classList.add('modified');
            });

            // Add subtle animation to indicate change
            row.style.background = 'linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)';
            setTimeout(() => {
                row.style.background = '';
            }, 1000);
        }
        this.updateStats();
    }

    updateAvailabilityStyle(selectElement) {
        const value = selectElement.value;
        selectElement.className = `availability-select ${value}`;
    }

    autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }

    checkImageAvailability(imageUrl) {
        // Simple check - in real app, you might want to check if image actually loads
        return imageUrl && imageUrl.trim() !== '';
    }

    openImagePreview(imageUrl) {
        if (imageUrl) {
            window.open(imageUrl, '_blank');
        }
    }

    openProductUrl(index) {
        const product = this.products[index];
        const productUrl = product?.source_url || product?.url;
        if (product && productUrl) {
            window.open(productUrl, '_blank');
            this.showNotification('Opening product page...', 'success');
        } else {
            this.showNotification('No product URL available', 'error');
        }
    }

    removeImage(productIndex, imageIndex) {
        if (confirm('Are you sure you want to remove this image?')) {
            this.products[productIndex].product_images.splice(imageIndex, 1);
            this.markModified(productIndex);
            this.renderTable();
            this.showNotification('Image removed successfully!', 'success');
        }
    }

    addImage(productIndex) {
        const imageUrl = prompt('Enter image URL:');
        if (imageUrl && imageUrl.trim()) {
            const trimmedUrl = imageUrl.trim();
            if (this.isValidImageUrl(trimmedUrl)) {
                this.products[productIndex].product_images.push(trimmedUrl);
                this.markModified(productIndex);
                this.renderTable();
                this.showNotification('Image added successfully!', 'success');
            } else {
                this.showNotification('Please enter a valid image URL', 'error');
            }
        }
    }

    isValidImageUrl(url) {
        try {
            new URL(url);
            return /\.(jpg|jpeg|png|gif|bmp|webp|svg)(\?.*)?$/i.test(url) ||
                url.includes('cdn.shop') || url.includes('shopify');
        } catch {
            return false;
        }
    }

    showAllImages(productIndex) {
        const product = this.products[productIndex];
        const images = product.product_images || [];

        if (images.length === 0) {
            this.showNotification('No images available', 'error');
            return;
        }

        const modal = document.createElement('div');
        modal.className = 'loading-overlay';
        modal.innerHTML = `
                    <div class="loading-content" style="max-width: 80%; max-height: 80%; overflow-y: auto; text-align: left;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; position: sticky; top: 0; background: white; z-index: 1;">
                            <h3 style="margin: 0; color: var(--text-primary);">
                                <i class="fas fa-images" style="margin-right: 8px; color: var(--accent-purple);"></i>
                                All Images for: ${product.product_name || 'Product'}
                            </h3>
                            <button onclick="document.body.removeChild(this.closest('.loading-overlay'))" 
                                    style="background: none; border: none; font-size: 1.5rem; cursor: pointer; color: var(--text-secondary);">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 16px;">
                            ${images.map((img, imgIndex) => `
                                <div style="position: relative; border: 1px solid var(--border-light); border-radius: 8px; overflow: hidden;">
                                    <img src="${img}" style="width: 100%; height: 120px; object-fit: cover;" 
                                         onclick="window.open('${img}', '_blank')"
                                         onerror="this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTUwIiBoZWlnaHQ0iIxMjAiIHZpZXdCb3g9IjAgMCAxNTAgMTIwIiBmaWxsPSJub25lIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPgo8cmVjdCB3aWR0aD0iMTUwIiBoZWlnaHQ9IjEyMCIgZmlsbD0iI0YxRjVGOSIvPgo8dGV4dCB4PSI3NSIgeT0iNjUiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZpbGw9IiNDQkQ1RTEiIGZvbnQtc2l6ZT0iMTIiPkltYWdlIEVycm9yPC90ZXh0Pgo8L3N2Zz4K'">
                                    <div style="position: absolute; top: 4px; right: 4px;">
                                        <button onclick="productEditor.removeImageFromModal(${productIndex}, ${imgIndex}); document.body.removeChild(this.closest('.loading-overlay')); productEditor.renderTable();" 
                                                style="background: #ef4444; color: white; border: none; border-radius: 50%; width: 24px; height: 24px; cursor: pointer; display: flex; align-items: center; justify-content: center;">
                                            <i class="fas fa-times"></i>
                                        </button>
                                    </div>
                                    <div style="padding: 8px; background: white; border-top: 1px solid var(--border-light); font-size: 0.8rem; color: var(--text-secondary);">
                                        Image ${imgIndex + 1}
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `;

        document.body.appendChild(modal);
    }

    removeImageFromModal(productIndex, imageIndex) {
        this.products[productIndex].product_images.splice(imageIndex, 1);
        this.markModified(productIndex);
        this.showNotification('Image removed successfully!', 'success');
    }

    duplicateRow(index) {
        const productToDuplicate = { ...this.products[index] };
        productToDuplicate.product_name = (productToDuplicate.product_name || '') + ' (Copy)';

        this.products.push(productToDuplicate);
        this.renderTable();
        this.updateStats();
        this.showNotification('Product duplicated successfully!', 'success');
    }

    deleteRow(index) {
        if (confirm('Are you sure you want to delete this product?')) {
            this.products.splice(index, 1);
            this.modifiedRows.delete(index);
            this.renderTable();
            this.updateStats();
            this.showNotification('Product deleted successfully!', 'success');
        }
    }

    updateStats() {
        const totalProducts = this.products.length;
        const modifiedProducts = this.modifiedRows.size;
        const selectedProducts = document.querySelectorAll('.row-checkbox:checked').length;

        // Count premium products
        const premiumProducts = document.querySelectorAll('.premium-toggle input:checked').length;

        document.getElementById('totalProducts').textContent = totalProducts;
        document.getElementById('modifiedProducts').textContent = modifiedProducts;
        document.getElementById('selectedProducts').textContent = selectedProducts;
        document.getElementById('premiumProducts').textContent = premiumProducts;
    }

    showNotification(message, type = 'success') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `<i class="fas fa-${type === 'success' ? 'check' : 'exclamation-triangle'}"></i> ${message}`;

        document.body.appendChild(notification);

        setTimeout(() => notification.classList.add('show'), 100);
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => document.body.removeChild(notification), 300);
        }, 3000);
    }
collectProductData() {
    const rows = document.querySelectorAll('#productsTableBody tr');
    const products = [];

    rows.forEach((row, index) => {
        const cells = row.querySelectorAll('.editable-cell');
        const availabilitySelect = row.querySelector('.availability-select');
        const premiumToggle = row.querySelector('.premium-toggle input');

        const product = {
            product_name: cells[0].value.trim(),
            price: parseFloat(cells[1].value) || 0,
            discounted_price: parseFloat(cells[2].value) || 0,
            premium: premiumToggle.checked,
            availability: availabilitySelect.value,
            description: cells[3].value.trim(),
            sizes: this.getCurrentValues('sizes', index),
            colors: this.getCurrentValues('colors', index),
            material: this.getCurrentValues('materials', index)[0] || '',
            categories: this.getCurrentValues('categories', index),
            product_images: this.products[index].product_images || [],
            url: this.products[index].url || '',
            source_url: this.products[index].source_url || '',
            timestamp: new Date().toISOString(),
            extraction_method: 'manual_edit',
            weight: 0 // Default weight, will be updated during upload
        };
        products.push(product);
    });

    return products;
}



// Add this method to the ProductEditor class
positionDropdown(menu, toggle) {
    const rect = toggle.getBoundingClientRect();
    const menuHeight = menu.offsetHeight;
    const spaceBelow = window.innerHeight - rect.bottom;
    
    // Position above if not enough space below
    if (spaceBelow < menuHeight && rect.top > menuHeight) {
        menu.style.top = 'auto';
        menu.style.bottom = `${window.innerHeight - rect.top}px`;
    } else {
        menu.style.top = `${rect.bottom}px`;
        menu.style.bottom = 'auto';
    }
    
    menu.style.left = `${rect.left}px`;
    menu.style.minWidth = `${rect.width}px`;
}

toggleDropdown(dropdownId, event) {
    if (event) event.stopPropagation();
    
    const dropdown = document.getElementById(dropdownId);
    if (!dropdown) return;
    
    const menu = dropdown.querySelector('.dropdown-menu');
    const toggle = dropdown.querySelector('.dropdown-toggle');
    const isOpen = menu.classList.contains('show');
    
    // Close all other dropdowns first
    document.querySelectorAll('.dropdown-menu.show').forEach(m => {
        m.classList.remove('show');
        m.closest('.dropdown-container').querySelector('.dropdown-toggle').classList.remove('active');
    });
    
    if (!isOpen) {
        menu.classList.add('show');
        toggle.classList.add('active');
        
        // Position the dropdown properly
        this.positionDropdown(menu, toggle);
        
        // Focus the search input if it exists
        const searchInput = menu.querySelector('input[type="text"]');
        if (searchInput) {
            setTimeout(() => searchInput.focus(), 100);
        }
        
        // Add backdrop for mobile
        if (window.innerWidth <= 768) {
            this.addMobileBackdrop(dropdownId);
        }
    } else {
        menu.classList.remove('show');
        toggle.classList.remove('active');
        this.removeMobileBackdrop();
    }
}
    // Add these methods to the ProductEditor class
// toggleDropdown(dropdownId, event) {
//         if (event) event.stopPropagation();
        
//         const dropdown = document.getElementById(dropdownId);
//         if (!dropdown) return;
        
//         const menu = dropdown.querySelector('.dropdown-menu');
//         const toggle = dropdown.querySelector('.dropdown-toggle');
//         const isOpen = menu.classList.contains('show');
        
//         // Close all other dropdowns first
//         document.querySelectorAll('.dropdown-menu.show').forEach(m => {
//             m.classList.remove('show');
//             m.closest('.dropdown-container').querySelector('.dropdown-toggle').classList.remove('active');
//         });
        
//         if (!isOpen) {
//             menu.classList.add('show');
//             toggle.classList.add('active');
            
//             // Focus the search input if it exists
//             const searchInput = menu.querySelector('input[type="text"]');
//             if (searchInput) {
//                 setTimeout(() => searchInput.focus(), 100);
//             }
            
//             // Add backdrop for mobile
//             if (window.innerWidth <= 768) {
//                 this.addMobileBackdrop(dropdownId);
//             }
//         } else {
//             menu.classList.remove('show');
//             toggle.classList.remove('active');
//             this.removeMobileBackdrop();
//         }
//     }
    
    filterDropdownOptions(dropdownId, searchText) {
        const dropdown = document.getElementById(dropdownId);
        if (!dropdown) return;
        
        const options = dropdown.querySelectorAll('.dropdown-item');
        const searchLower = searchText.toLowerCase().trim();
        
        let visibleCount = 0;
        options.forEach(option => {
            const text = option.textContent.toLowerCase();
            const matches = text.includes(searchLower);
            option.style.display = matches ? 'flex' : 'none';
            if (matches) visibleCount++;
        });
        
        // Show "no results" message if needed
        const optionsContainer = dropdown.querySelector('.dropdown-options');
        if (visibleCount === 0) {
            if (!optionsContainer.querySelector('.no-results')) {
                const noResults = document.createElement('div');
                noResults.className = 'no-results';
                noResults.style.cssText = 'padding: 20px; text-align: center; color: #9ca3af; font-style: italic; font-size: 0.75rem;';
                noResults.textContent = `No results for "${searchText}"`;
                optionsContainer.appendChild(noResults);
            }
        } else {
            const noResults = optionsContainer.querySelector('.no-results');
            if (noResults) noResults.remove();
        }
    }
    
    selectOption(field, index, value, multiple) {
        let currentValues = this.getCurrentValues(field, index);
        
        if (multiple) {
            // Toggle selection for multiple select
            if (currentValues.includes(value)) {
                currentValues = currentValues.filter(v => v !== value);
            } else {
                currentValues.push(value);
            }
        } else {
            // Single select - replace current value
            currentValues = [value];
            
            // Close the dropdown after single selection
            const dropdownId = `${field}-dropdown-${index}`;
            const dropdown = document.getElementById(dropdownId);
            if (dropdown) {
                dropdown.querySelector('.dropdown-menu').classList.remove('show');
                dropdown.querySelector('.dropdown-toggle').classList.remove('active');
            }
        }
        
        this.updateProductValue(field, currentValues, index);
        this.markModified(index);
        
        // Update the dropdown display without full re-render
        this.updateDropdownDisplay(field, index, currentValues);
    }
    
    removeOption(field, index, value) {
        const currentValues = this.getCurrentValues(field, index);
        const updatedValues = currentValues.filter(v => v !== value);
        
        this.updateProductValue(field, updatedValues, index);
        this.markModified(index);
        
        // Update the dropdown display without full re-render
        this.updateDropdownDisplay(field, index, updatedValues);
    }
    
    updateDropdownDisplay(field, index, values) {
        const dropdownId = `${field}-dropdown-${index}`;
        const dropdown = document.getElementById(dropdownId);
        if (!dropdown) return;
        
        const toggle = dropdown.querySelector('.dropdown-toggle');
        const selectedText = toggle.querySelector('.selected-text');
        const selectedOptions = dropdown.querySelector('.selected-options');
        
        // Update toggle text
        if (values.length > 0) {
            selectedText.textContent = `${values.length} selected`;
            selectedText.classList.remove('placeholder');
            toggle.classList.add('has-selection');
        } else {
            selectedText.textContent = `Select ${field}`;
            selectedText.classList.add('placeholder');
            toggle.classList.remove('has-selection');
        }
        
        // Update selected tags if multiple
        if (selectedOptions) {
            const options = optionsData[field] || [];
            const tagsHTML = values.map(value => {
                if (field === 'colors') {
                    const colorOption = options.find(opt => 
                        (opt.option_value_name || opt.name || opt) === value
                    );
                    const colorCode = colorOption?.color_code || '#ccc';
                    return `
                        <div class="selected-tag">
                            <span class="color-box" style="background-color: ${colorCode}"></span>
                            <span class="truncated-text">${value}</span>
                            <span class="remove" onclick="event.stopPropagation(); productEditor.removeOption('${field}', ${index}, '${value}')">×</span>
                        </div>
                    `;
                }
                return `
                    <div class="selected-tag">
                        <span class="truncated-text">${value}</span>
                        <span class="remove" onclick="event.stopPropagation(); productEditor.removeOption('${field}', ${index}, '${value}')">×</span>
                    </div>
                `;
            }).join('');
            selectedOptions.innerHTML = tagsHTML;
        }
        
        // Update checkmarks in dropdown items
        const items = dropdown.querySelectorAll('.dropdown-item');
        items.forEach(item => {
            const itemValue = item.getAttribute('data-value');
            const isSelected = values.includes(itemValue);
            const checkIcon = item.querySelector('.fa-check');
            
            if (isSelected) {
                item.classList.add('selected');
                if (checkIcon) checkIcon.style.opacity = '1';
            } else {
                item.classList.remove('selected');
                if (checkIcon) checkIcon.style.opacity = '0';
            }
        });
    }
    
    addMobileBackdrop(dropdownId) {
        let backdrop = document.querySelector('.dropdown-backdrop');
        if (!backdrop) {
            backdrop = document.createElement('div');
            backdrop.className = 'dropdown-backdrop show';
            backdrop.onclick = () => {
                this.closeAllDropdowns();
                this.removeMobileBackdrop();
            };
            document.body.appendChild(backdrop);
        }
    }
    
    removeMobileBackdrop() {
        const backdrop = document.querySelector('.dropdown-backdrop');
        if (backdrop) {
            backdrop.remove();
        }
    }
    
    closeAllDropdowns() {
        document.querySelectorAll('.dropdown-menu.show').forEach(menu => {
            menu.classList.remove('show');
            menu.closest('.dropdown-container').querySelector('.dropdown-toggle').classList.remove('active');
        });
        this.removeMobileBackdrop();
    }
}

    // Toggle image sizes dropdown
    function toggleImageSizes(button) {
        const dropdown = button.nextElementSibling;
        const isOpen = dropdown.classList.contains('show');

        // Close all open dropdowns first
        document.querySelectorAll('.image-sizes-dropdown-content').forEach(content => {
            content.classList.remove('show');
        });

        document.querySelectorAll('.image-sizes-toggle').forEach(toggle => {
            toggle.classList.remove('open');
        });

        // Toggle this dropdown if it wasn't open
        if (!isOpen) {
            dropdown.classList.add('show');
            button.classList.add('open');
        }

        // Stop propagation to prevent immediate document click
        event.stopPropagation();
    }


function addNewProduct() {
    const newProduct = {
        product_name: 'New Product',
        price: 0,
        discounted_price: 0,
        premium: false,
        availability: 'in-stock',
        description: '',
        sizes: [],
        colors: [],
        material: '',
        categories: [],
        product_images: [],
        url: '',
        timestamp: new Date().toISOString(),
        extraction_method: 'manual_add'
    };

    productEditor.products.push(newProduct);
    productEditor.renderTable();
    productEditor.updateStats();
    productEditor.showNotification('New product added!', 'success');
}

function resetChanges() {
    if (confirm('Are you sure you want to reset all changes? This will restore the original data.')) {
        productEditor.products = JSON.parse(JSON.stringify(productEditor.originalProducts));
        productEditor.modifiedRows.clear();
        productEditor.renderTable();
        productEditor.updateStats();
        productEditor.showNotification('Changes reset successfully!', 'success');
    }
}

function saveChanges() {
    const updatedProducts = productEditor.collectProductData();
    localStorage.setItem('selectedProducts', JSON.stringify(updatedProducts));
    productEditor.modifiedRows.clear();
    productEditor.renderTable();
    productEditor.updateStats();
    productEditor.showNotification('Changes saved successfully!', 'success');
}

function exportData() {
    const products = productEditor.collectProductData();
    const csvContent = convertToCSV(products);
    downloadCSV(csvContent, 'products.csv');
    productEditor.showNotification('CSV exported successfully!', 'success');
}

function convertToCSV(products) {
    if (products.length === 0) return '';

    const headers = ['Product Name', 'Price', 'Discounted Price', 'Premium', 'Availability', 'Description', 'Sizes', 'Colors', 'Material', 'Categories', 'Image URLs'];
    const csvRows = [headers.join(',')];

    products.forEach(product => {
        const row = [
            `"${product.product_name || ''}"`,
            product.price || 0,
            product.discounted_price || 0,
            product.premium ? 'Yes' : 'No',
            `"${product.availability || 'in-stock'}"`,
            `"${product.description || ''}"`,
            `"${Array.isArray(product.sizes) ? product.sizes.join(', ') : ''}"`,
            `"${Array.isArray(product.colors) ? product.colors.join(', ') : ''}"`,
            `"${product.material || ''}"`,
            `"${Array.isArray(product.categories) ? product.categories.join(', ') : ''}"`,
            `"${Array.isArray(product.product_images) ? product.product_images.join(' | ') : ''}"`
        ];
        csvRows.push(row.join(','));
    });

    return csvRows.join('\n');
}

function downloadCSV(csvContent, filename) {
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Add this function to fetch product weight
// Alternative implementation using query parameters
// Enhanced function to fetch product weight with better error handling
async function fetchProductWeight(categoryName) {
    try {
        console.log(`Fetching weight for category: ${categoryName}`);
        
        const response = await fetch('https://www.dasds.in/api/option/product-weight', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ categoryName })
        });

        if (!response.ok) {
            console.error(`HTTP error! status: ${response.status}`);
            return 0;
        }
        
        const data = await response.json();
        console.log('Weight API response:', data);
        
        // Check different possible response structures
        if (data.success && data.weight !== undefined) {
            return data.weight;
        } else if (data.data && data.data.weight !== undefined) {
            return data.data.weight;
        } else if (data.weight !== undefined) {
            return data.weight;
        } else {
            console.error('Unexpected API response format:', data);
            return 0;
        }
    } catch (error) {
        console.error('Error fetching product weight:', error);
        return 0;
    }
}

// Update the uploadProducts function to log more details
async function uploadProducts() {
    const products = productEditor.collectProductData();

    if (products.length === 0) {
        alert('No products to upload.');
        return;
    }

    if (!confirm(`Are you sure you want to upload ${products.length} products?`)) {
        return;
    }

    const loadingOverlay = document.getElementById('loadingOverlay');
    loadingOverlay.style.display = 'flex';

    try {
        // Add product weights based on categories
        const productsWithWeights = [];
        
        for (const [index, product] of products.entries()) {
            // Get the first category (or use all categories joined)
            let categoryName = '';
            
            if (Array.isArray(product.categories) && product.categories.length > 0) {
                categoryName = product.categories[0];
                console.log(`Processing product ${index + 1}: ${product.product_name}`);
                console.log(`Category: ${categoryName}`);
            } else if (product.categories) {
                categoryName = product.categories;
            }
            
            // Only fetch weight if we have a category
            let weight = 0;
            if (categoryName) {
                weight = await fetchProductWeight(categoryName);
                console.log(`Weight for ${categoryName}: ${weight}`);
            } else {
                console.log(`No category found for product: ${product.product_name}`);
            }
            
            // Create product with weight
            const productWithWeight = {
                ...product,
                weight: weight
            };
            
            productsWithWeights.push(productWithWeight);
        }

        // Remove image_sizes property from each product
        const productsWithoutImageSizes = productsWithWeights.map(product => {
            const { image_sizes, ...productWithoutSizes } = product;
            return productWithoutSizes;
        });

        // Prepare the upload data
        const uploadData = {
            products: productsWithoutImageSizes,
            metadata: {
                timestamp: new Date().toISOString(),
                total_products: productsWithoutImageSizes.length,
                upload_type: "manual_edit",
                source: "edit_interface",
                weights_included: true
            }
        };

        console.log('Final upload data:', uploadData);

        // Send to the backend API
        const response = await fetch('/api/upload-products', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(uploadData)
        });

        const result = await response.json();

        if (result.success) {
            productEditor.showNotification(
                `Successfully uploaded ${productsWithoutImageSizes.length} products with weights!`, 
                'success'
            );
            
            // Clear localStorage after successful upload
            localStorage.removeItem('selectedProducts');
        } else {
            throw new Error(result.error || 'Upload failed');
        }
    } catch (error) {
        console.error('Upload error:', error);
        productEditor.showNotification(`Upload failed: ${error.message}`, 'error');
    } finally {
        loadingOverlay.style.display = 'none';
    }
}
// Function to fetch options data from the API
async function fetchOptionsDataFromAPI() {
    try {
        const response = await fetch('https://www.zotik.in/api/option/all-options');
        const data = await response.json();

        if (data.status) {
            // Extract and format the options data
            const colorOptions = data.data.colorOptions[0].option_values;
            const sizeOptions = data.data.sizeOptions[0].option_values;
            const materialOptions = data.data.materialOptions[0].option_values;
            const categories = data.data.allCategories;

            return {
                colors: colorOptions.map(opt => opt.option_value_name),
                sizes: sizeOptions.map(opt => opt.option_value_name),
                materials: materialOptions.map(opt => opt.option_value_name),
                categories: categories.map(cat => cat.category_name)
            };
        } else {
            throw new Error(data.message || 'Failed to fetch options data');
        }
    } catch (error) {
        console.error('Error fetching options data:', error);
        // Return fallback data if API fails
        return {
            colors: ['Red', 'Blue', 'Green', 'Black', 'White'],
            sizes: ['S', 'M', 'L', 'XL', 'XXL'],
            materials: ['Cotton', 'Polyester', 'Silk', 'Wool'],
            categories: ['Clothing', 'Accessories', 'Footwear']
        };
    }
}

function toggleKeyboardHelp() {
    const modal = document.getElementById('keyboardHelpModal');
    modal.style.display = modal.style.display === 'none' ? 'flex' : 'none';
}


// Add to edit_products.js after the optionsData declaration
function createDropdown(field, index, multiple = true) {
    const product = productEditor.products[index];
    const currentValues = productEditor.getCurrentValues(field, index);
    const options = optionsData[field] || [];
    const dropdownId = `${field}-dropdown-${index}`;
    
    // For Material field, ensure we only use API values
    let materialOptions = [];
    if (field === 'materials') {
        materialOptions = optionsData.materials.map(opt => 
            typeof opt === 'object' ? opt.option_value_name : opt
        );
    }
    
    // Determine placeholder text
    let placeholderText = 'Select options';
    if (field === 'materials') {
        placeholderText = 'Select material';
    } else if (field === 'categories') {
        placeholderText = 'Select categories';
    } else if (field === 'sizes') {
        placeholderText = 'Select sizes';
    } else if (field === 'colors') {
        placeholderText = 'Select colors';
    }
    
    // Create display text for toggle button
    let displayText = placeholderText;
    let hasSelection = false;
    
    if (currentValues.length > 0) {
        hasSelection = true;
        if (!multiple) {
            displayText = currentValues[0];
        } else {
            displayText = `${currentValues.length} selected`;
        }
    }
    
    // Create options HTML - use materialOptions for materials field
    const optionsToUse = field === 'materials' ? materialOptions : options;
    const optionsHTML = optionsToUse.map(option => {
        let optionValue, optionDisplay, colorCode = null;
        
        // Handle different option structures
        if (typeof option === 'object') {
            optionValue = option.option_value_name || option.category_name || option.name || option;
            optionDisplay = optionValue;
            colorCode = option.color_code || null;
        } else {
            optionValue = option;
            optionDisplay = option;
        }
        
        const isSelected = currentValues.includes(optionValue);
        
        if (field === 'colors' && colorCode) {
            return `
                <div class="dropdown-item ${isSelected ? 'selected' : ''}" 
                     data-value="${optionValue}"
                     onclick="event.stopPropagation(); productEditor.selectOption('${field}', ${index}, '${optionValue}', ${multiple})">
                    <div class="color-option">
                        <div class="color-box" style="background-color: ${colorCode || '#ccc'}"></div>
                        <span>${optionDisplay}</span>
                    </div>
                    <i class="fas fa-check" style="${isSelected ? '' : 'opacity: 0;'}"></i>
                </div>
            `;
        }
        
        return `
            <div class="dropdown-item ${isSelected ? 'selected' : ''}" 
                 data-value="${optionValue}"
                 onclick="event.stopPropagation(); productEditor.selectOption('${field}', ${index}, '${optionValue}', ${multiple})">
                <span>${optionDisplay}</span>
                <i class="fas fa-check" style="${isSelected ? '' : 'opacity: 0;'}"></i>
            </div>
        `;
    }).join('');
    
    // Create selected tags HTML
    const selectedTagsHTML = currentValues.map(value => {
        if (field === 'colors') {
            const colorOption = options.find(opt => 
                (opt.option_value_name || opt.name || opt) === value
            );
            const colorCode = colorOption?.color_code || '#ccc';
            return `
                <div class="selected-tag">
                    <span class="color-box" style="background-color: ${colorCode}"></span>
                    <span class="truncated-text">${value}</span>
                    <span class="remove" onclick="event.stopPropagation(); productEditor.removeOption('${field}', ${index}, '${value}')">×</span>
                </div>
            `;
        }
        return `
            <div class="selected-tag">
                <span class="truncated-text">${value}</span>
                <span class="remove" onclick="event.stopPropagation(); productEditor.removeOption('${field}', ${index}, '${value}')">×</span>
            </div>
        `;
    }).join('');
    
    return `
        <div class="dropdown-container" id="${dropdownId}">
            <button class="dropdown-toggle ${hasSelection ? 'has-selection' : ''}" 
                    onclick="event.stopPropagation(); productEditor.toggleDropdown('${dropdownId}', event)"
                    type="button">
                <span class="selected-text ${!hasSelection ? 'placeholder' : ''}">${displayText}</span>
                <i class="fas fa-chevron-down"></i>
            </button>
            <div class="dropdown-menu" onclick="event.stopPropagation()" data-field="${field}">
                <div class="dropdown-search">
                    <input type="text" 
                           placeholder="Search ${field}..." 
                           onclick="event.stopPropagation()"
                           oninput="productEditor.filterDropdownOptions('${dropdownId}', this.value)">
                </div>
                <div class="dropdown-options">
                    ${optionsHTML || '<div style="padding: 20px; text-align: center; color: #9ca3af;">No options available</div>'}
                </div>
            </div>
            ${multiple ? `<div class="selected-options">${selectedTagsHTML}</div>` : ''}
        </div>
    `;
}




// Initialize the editor
let productEditor;
document.addEventListener('DOMContentLoaded', async () => {
    productEditor = new ProductEditor();
    await productEditor.init();

    // Add keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd + S to save
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            saveChanges();
            productEditor.showNotification('Changes saved with Ctrl+S!', 'success');
        }

        // Ctrl/Cmd + E to export
        if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
            e.preventDefault();
            exportData();
            productEditor.showNotification('Data exported with Ctrl+E!', 'success');
        }

        // Escape to clear focus
        if (e.key === 'Escape') {
            document.activeElement.blur();
        }
        
    });

    // Auto-save every 30 seconds
    setInterval(() => {
        if (productEditor.modifiedRows.size > 0) {
            saveChanges();
            productEditor.showNotification('Auto-saved changes', 'success');
        }
    }, 30000);
    
});
document.addEventListener('click', (e) => {
    if (!e.target.closest('.dropdown-container')) {
        if (productEditor) {
            productEditor.closeAllDropdowns();
        }
    }
});
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        if (productEditor) {
            productEditor.closeAllDropdowns();
        }
    }
});

