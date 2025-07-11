document.addEventListener('DOMContentLoaded', () => {
    // Flaskから渡されたlocation_countsデータを取得
    const locationCountsElement = document.getElementById('location-counts-data');
    const locationCounts = JSON.parse(locationCountsElement.textContent);

    // 各グリッドセルに在庫数を表示
    for (const locationName in locationCounts) {
        const count = locationCounts[locationName];
        const targetCell = document.getElementById(locationName);
        if (targetCell) {
            // 既存のzone-nameを保持しつつ、在庫数を追加
            let zoneNameSpan = targetCell.querySelector('.zone-name');
            if (!zoneNameSpan) {
                zoneNameSpan = document.createElement('span');
                zoneNameSpan.className = 'zone-name';
                zoneNameSpan.textContent = locationName;
                targetCell.prepend(zoneNameSpan);
            }
            const countSpan = document.createElement('span');
            countSpan.className = 'item-count';
            countSpan.textContent = count;
            targetCell.appendChild(countSpan);
        }
    }

    // ドラッグ＆ドロップ機能は、このアプリケーションのバックエンドと連携しないため、
    // 現在のところは無効化または削除します。
    // 必要であれば、後でサーバーサイドと連携する形で再実装を検討します。

    // 既存のドラッグ＆ドロップ関連のイベントリスナーを削除またはコメントアウト
    const dropzones = document.querySelectorAll('.dropzone');
    dropzones.forEach(zone => {
        zone.addEventListener('dragover', (e) => { e.preventDefault(); /* zone.classList.add('drag-over'); */ });
        zone.addEventListener('dragleave', () => { /* zone.classList.remove('drag-over'); */ });
        zone.addEventListener('drop', (e) => { e.preventDefault(); /* zone.classList.remove('drag-over'); */ });
    });
});