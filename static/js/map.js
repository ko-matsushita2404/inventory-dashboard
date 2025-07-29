document.addEventListener('DOMContentLoaded', function() {
    // Get the modal element and its body
    const locationModal = new bootstrap.Modal(document.getElementById('locationModal'));
    const modalTitle = document.getElementById('locationModalLabel');
    const modalBody = document.getElementById('locationModalBody');

    // Get data from the script tags
    const itemsDataElement = document.getElementById('location-items-data');
    const productNumbersDataElement = document.getElementById('location-product-numbers-data');

    if (!itemsDataElement || !productNumbersDataElement) {
        console.error('Error: Data elements not found');
        return;
    }

    const locationItems = JSON.parse(itemsDataElement.textContent);
    const locationProductNumbers = JSON.parse(productNumbersDataElement.textContent);

    // Populate product numbers in cells
    for (const locationId in locationProductNumbers) {
        const productNumbers = locationProductNumbers[locationId];
        const cell = document.getElementById(locationId);
        if (cell) {
            const productNumbersSpan = cell.querySelector('.product-numbers');
            if (productNumbersSpan) {
                productNumbersSpan.textContent = productNumbers.join(', ');
            }

            // Add click event listener to each cell
            cell.addEventListener('click', function() {
                const itemsInLocation = locationItems[locationId];
                if (itemsInLocation && itemsInLocation.length > 0) {
                    // Set the modal title
                    modalTitle.textContent = `保管場所: ${locationId}`;

                    // Clear previous content and build the new list
                    modalBody.innerHTML = '';
                    const list = document.createElement('ul');
                    list.className = 'list-group';

                    itemsInLocation.forEach(item => {
                        const listItem = document.createElement('a');
                        listItem.href = `/item/${item.id}`;
                        listItem.className = 'list-group-item list-group-item-action';
                        listItem.textContent = `製番: ${item.production_no}`;
                        list.appendChild(listItem);
                    });

                    modalBody.appendChild(list);

                    // Show the modal
                    locationModal.show();
                }
            });
        }
    }
});