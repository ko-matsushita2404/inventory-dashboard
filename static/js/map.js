document.addEventListener('DOMContentLoaded', function () {
    const locationModal = new bootstrap.Modal(document.getElementById('locationModal'));
    const modalTitle = document.getElementById('locationModalLabel');
    const modalBody = document.getElementById('locationModalBody');

    const itemsDataElement = document.getElementById('location-items-data');
    const productNumbersDataElement = document.getElementById('location-product-numbers-data');

    if (!itemsDataElement || !productNumbersDataElement) {
        console.error('Error: Data elements not found');
        return;
    }

    const locationItems = JSON.parse(itemsDataElement.textContent);
    const locationProductNumbers = JSON.parse(productNumbersDataElement.textContent);

    // Populate product numbers in cells and add click listeners
    for (const locationId in locationProductNumbers) {
        const productNumbers = locationProductNumbers[locationId];
        const cell = document.getElementById(locationId);
        if (cell) {
            const productNumbersSpan = cell.querySelector('.product-numbers');
            if (productNumbersSpan) {
                productNumbersSpan.textContent = productNumbers.join(', ');
            }

            // Click event for modal
            cell.addEventListener('click', function () {
                const itemsInLocation = locationItems[locationId];
                if (itemsInLocation && itemsInLocation.length > 0) {
                    modalTitle.textContent = `保管場所: ${locationId}`;
                    modalBody.innerHTML = '';

                    const groupedByProduction = {};
                    itemsInLocation.forEach(item => {
                        const prodNo = item.production_no;
                        if (!groupedByProduction[prodNo]) {
                            groupedByProduction[prodNo] = { production_no: prodNo, items: [] };
                        }
                        groupedByProduction[prodNo].items.push(item);
                    });

                    const container = document.createElement('div');
                    container.className = 'production-groups';

                    for (const prodNo in groupedByProduction) {
                        const group = groupedByProduction[prodNo];

                        const groupDiv = document.createElement('div');
                        groupDiv.className = 'd-flex justify-content-between align-items-center mb-2';

                        const prodNoSpan = document.createElement('span');
                        prodNoSpan.className = 'fw-bold fs-5';
                        prodNoSpan.textContent = `製番: ${prodNo}`;

                        // --- Button Group ---
                        const buttonGroup = document.createElement('div');
                        buttonGroup.className = 'btn-group';
                        buttonGroup.setAttribute('role', 'group');

                        // Details Button (Location Specific)
                        const detailsButton = document.createElement('a');
                        detailsButton.href = `/production/${prodNo}/location/${locationId}`;
                        detailsButton.target = '_blank';
                        detailsButton.className = 'btn btn-info btn-sm';
                        detailsButton.innerHTML = '<i class="bi bi-info-circle"></i> 詳細';
                        detailsButton.title = 'この場所の部品詳細を開く';

                        // Move Button
                        const moveButton = document.createElement('a');
                        moveButton.href = `/move/location/${locationId}/production/${prodNo}`;
                        moveButton.className = 'btn btn-warning btn-sm';
                        moveButton.innerHTML = '<i class="bi bi-arrows-move"></i> 移動';
                        moveButton.title = 'この製番をまとめて移動';

                        buttonGroup.appendChild(detailsButton);
                        buttonGroup.appendChild(moveButton);

                        groupDiv.appendChild(prodNoSpan);
                        groupDiv.appendChild(buttonGroup);
                        container.appendChild(groupDiv);
                    }

                    modalBody.appendChild(container);
                    locationModal.show();
                }
            });
        }
    }
});