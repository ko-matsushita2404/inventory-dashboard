document.addEventListener('DOMContentLoaded', function () {
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
            cell.addEventListener('click', function () {
                const itemsInLocation = locationItems[locationId];
                if (itemsInLocation && itemsInLocation.length > 0) {
                    // Set the modal title
                    modalTitle.textContent = `保管場所: ${locationId}`;

                    // Clear previous content and build the new list
                    modalBody.innerHTML = '';

                    // Group items by production_no
                    const groupedByProduction = {};
                    itemsInLocation.forEach(item => {
                        const prodNo = item.production_no;
                        if (!groupedByProduction[prodNo]) {
                            groupedByProduction[prodNo] = {
                                production_no: prodNo,
                                items: [],
                                total_quantity: 0
                            };
                        }
                        groupedByProduction[prodNo].items.push(item);
                        groupedByProduction[prodNo].total_quantity += item.remaining_quantity || 0;
                    });

                    // Create the grouped display
                    const container = document.createElement('div');
                    container.className = 'production-groups';

                    for (const prodNo in groupedByProduction) {
                        const group = groupedByProduction[prodNo];

                        // Create production number group header
                        const groupCard = document.createElement('div');
                        groupCard.className = 'card mb-3';

                        const cardHeader = document.createElement('div');
                        cardHeader.className = 'card-header d-flex justify-content-between align-items-center';

                        const headerContent = document.createElement('div');
                        headerContent.innerHTML = `
                            <strong>製番: ${prodNo}</strong>
                            <small class="text-muted ms-2">${group.items.length}件の部品</small>
                        `;

                        const buttonGroup = document.createElement('div');
                        buttonGroup.className = 'btn-group';

                        const moveButton = document.createElement('a');
                        moveButton.href = `/move/location/${locationId}/production/${prodNo}`;
                        moveButton.className = 'btn btn-warning btn-sm';
                        moveButton.innerHTML = '<i class="bi bi-arrows-move"></i> この製番をまとめて移動';

                        const quantityBadge = document.createElement('span');
                        quantityBadge.className = 'badge bg-primary';
                        quantityBadge.textContent = `総数量: ${group.total_quantity}`;

                        buttonGroup.appendChild(moveButton);

                        cardHeader.appendChild(headerContent);
                        cardHeader.appendChild(buttonGroup);
                        cardHeader.appendChild(quantityBadge);

                        // Create expandable item list
                        const cardBody = document.createElement('div');
                        cardBody.className = 'card-body';

                        const itemList = document.createElement('div');
                        itemList.className = 'list-group list-group-flush';

                        group.items.forEach(item => {
                            const listItem = document.createElement('a');
                            listItem.href = `/item/${item.id}`;
                            listItem.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';

                            const itemInfo = document.createElement('div');
                            itemInfo.innerHTML = `
                                <div class="fw-bold">${item.parts_name || '名称未設定'}</div>
                                <small class="text-muted">部品No: ${item.parts_no || '-'}</small>
                            `;

                            const quantitySpan = document.createElement('span');
                            quantitySpan.className = 'badge bg-success';
                            quantitySpan.textContent = `${item.remaining_quantity || 0}`;

                            listItem.appendChild(itemInfo);
                            listItem.appendChild(quantitySpan);
                            itemList.appendChild(listItem);
                        });

                        // Add "View All" link for production number
                        const viewAllLink = document.createElement('a');
                        viewAllLink.href = `/production/${prodNo}`;
                        viewAllLink.className = 'btn btn-outline-primary btn-sm mt-2';
                        viewAllLink.innerHTML = `<i class="bi bi-list-ul"></i> 製番 ${prodNo} の全詳細を表示`;

                        cardBody.appendChild(itemList);
                        cardBody.appendChild(viewAllLink);

                        groupCard.appendChild(cardHeader);
                        groupCard.appendChild(cardBody);
                        container.appendChild(groupCard);
                    }

                    modalBody.appendChild(container);

                    // Show the modal
                    locationModal.show();
                }
            });
        }
    }
});
