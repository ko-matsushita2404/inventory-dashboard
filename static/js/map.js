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

    // Populate product numbers in cells and add click/drop event listeners
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
                            groupedByProduction[prodNo] = {
                                production_no: prodNo,
                                items: [],
                            };
                        }
                        groupedByProduction[prodNo].items.push(item);
                    });

                    const container = document.createElement('div');
                    container.className = 'production-groups';

                    for (const prodNo in groupedByProduction) {
                        const group = groupedByProduction[prodNo];

                        const groupDiv = document.createElement('div');
                        groupDiv.className = 'd-flex justify-content-between align-items-center mb-2';
                        groupDiv.setAttribute('draggable', 'true'); // Make draggable
                        groupDiv.dataset.productionNo = prodNo; // Store production number
                        groupDiv.dataset.originalLocation = locationId; // Store original location

                        const prodNoSpan = document.createElement('span');
                        prodNoSpan.className = 'fw-bold fs-5';
                        prodNoSpan.textContent = `製番: ${prodNo}`;

                        const moveButton = document.createElement('a');
                        moveButton.href = `/move/location/${locationId}/production/${prodNo}`;
                        moveButton.className = 'btn btn-warning btn-sm';
                        moveButton.innerHTML = '<i class="bi bi-arrows-move"></i> この製番をまとめて移動';

                        groupDiv.appendChild(prodNoSpan);
                        groupDiv.appendChild(moveButton);
                        container.appendChild(groupDiv);
                    }

                    modalBody.appendChild(container);

                    const draggableProdNos = modalBody.querySelectorAll('[draggable="true"]');
                    draggableProdNos.forEach(draggable => {
                        draggable.addEventListener('dragstart', function (e) {
                            const prodNo = e.target.dataset.productionNo;
                            const originalLocation = e.target.dataset.originalLocation;
                            
                            // Set data for the drop event
                            e.dataTransfer.setData('text/plain', JSON.stringify({ productionNo: prodNo, originalLocation: originalLocation }));
                            e.dataTransfer.effectAllowed = 'move';
                            e.target.style.cursor = 'grabbing'; // Change cursor on drag

                            // Hide the modal so the user can see the map
                            locationModal.hide();
                        });

                        draggable.addEventListener('dragend', function (e) {
                            e.target.style.cursor = 'grab'; // Reset cursor
                        });
                    });

                    locationModal.show();
                }
            });

            // Drag and Drop event listeners for cells
            cell.addEventListener('dragover', function (e) {
                e.preventDefault(); // Allow drop
                e.dataTransfer.dropEffect = 'move';
                this.classList.add('drag-over'); // Visual feedback
            });

            cell.addEventListener('dragenter', function (e) {
                e.preventDefault();
                this.classList.add('drag-over');
            });

            cell.addEventListener('dragleave', function () {
                this.classList.remove('drag-over');
            });

            cell.addEventListener('drop', function (e) {
                e.preventDefault();
                this.classList.remove('drag-over');

                const data = JSON.parse(e.dataTransfer.getData('text/plain'));
                const productionNo = data.productionNo;
                const originalLocation = data.originalLocation;
                const newLocation = this.id; // The ID of the cell is the new location

                console.log(`Dropped ${productionNo} from ${originalLocation} to ${newLocation}`);

                if (originalLocation === newLocation) {
                    // No action needed if dropping in the same place
                    return;
                }

                // Check if the destination already contains the same production number
                const destProdNumbers = locationProductNumbers[newLocation] || [];
                if (destProdNumbers.includes(productionNo)) {
                    if (!confirm(`移動先 (${newLocation}) には既に同じ製番 (${productionNo}) が存在します。移動を続行しますか？`)) {
                        return; // User cancelled
                    }
                }

                // Send move request to server
                fetch('/move_production_dnd', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        production_no: productionNo,
                        original_location: originalLocation,
                        new_location: newLocation
                    }),
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert(data.message);
                        // Reload page or update UI to reflect changes
                        window.location.reload(); 
                    } else {
                        alert(`移動に失敗しました: ${data.message}`);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('移動中にエラーが発生しました。');
                });
            });
        }
    }
});