
document.addEventListener('DOMContentLoaded', function() {
    try {
        const dataElement = document.getElementById('location-product-numbers-data');
        if (!dataElement) {
            console.error('Error: Data element not found');
            return;
        }
        const data = JSON.parse(dataElement.textContent);
        for (const locationId in data) {
            const productNumbers = data[locationId];
            const cell = document.getElementById(locationId);
            if (cell) {
                const productNumbersSpan = cell.querySelector('.product-numbers');
                if (productNumbersSpan) {
                    productNumbersSpan.textContent = productNumbers.join(', ');
                }
            }
        }
    } catch (error) {
        console.error('Error loading product numbers for map:', error);
    }
});
