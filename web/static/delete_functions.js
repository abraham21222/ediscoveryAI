// Document Deletion Functions

function updateSelectionCount() {
    const checkboxes = document.querySelectorAll('.doc-checkbox:checked');
    const count = checkboxes.length;
    const deleteBtn = document.getElementById('deleteSelectedBtn');
    const countSpan = document.getElementById('selectedCount');
    
    countSpan.textContent = count;
    deleteBtn.style.display = count > 0 ? 'block' : 'none';
}

async function deleteSelectedDocuments() {
    const checkboxes = document.querySelectorAll('.doc-checkbox:checked');
    const docIds = Array.from(checkboxes).map(cb => cb.getAttribute('data-doc-id'));
    
    if (docIds.length === 0) {
        alert('No documents selected');
        return;
    }
    
    const confirmed = confirm(`⚠️ Are you sure you want to delete ${docIds.length} selected document(s)?\n\nThis action cannot be undone.`);
    if (!confirmed) return;
    
    try {
        const response = await fetch('/api/documents/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ document_ids: docIds })
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(`✅ Successfully deleted ${result.deleted_count} document(s)`);
            // Refresh the search to update the UI
            searchDocuments();
            // Reset selection
            updateSelectionCount();
        } else {
            alert(`❌ Error: ${result.error || 'Failed to delete documents'}`);
        }
    } catch (error) {
        console.error('Error deleting documents:', error);
        alert('❌ Failed to delete documents. Check console for details.');
    }
}

async function confirmDeleteAll() {
    const stats = document.getElementById('totalDocuments');
    const totalDocs = stats ? stats.textContent : '?';
    
    const confirmed = confirm(`⚠️⚠️⚠️ DANGER ⚠️⚠️⚠️\n\nYou are about to DELETE ALL ${totalDocs} documents from the database!\n\nThis action CANNOT be undone.\n\nAre you absolutely sure?`);
    if (!confirmed) return;
    
    const doubleConfirm = confirm(`⚠️ FINAL WARNING ⚠️\n\nType "yes" in the next prompt to confirm deletion of ALL documents.`);
    if (!doubleConfirm) return;
    
    const finalConfirm = prompt('Type "DELETE ALL" to confirm (case-sensitive):');
    if (finalConfirm !== 'DELETE ALL') {
        alert('Deletion cancelled - incorrect confirmation text');
        return;
    }
    
    try {
        const response = await fetch('/api/documents/delete-all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(`✅ Successfully deleted ${result.deleted_count} document(s) and ${result.related_records_deleted} related records.`);
            // Refresh the search to show empty state
            searchDocuments();
        } else {
            alert(`❌ Error: ${result.error || 'Failed to delete all documents'}`);
        }
    } catch (error) {
        console.error('Error deleting all documents:', error);
        alert('❌ Failed to delete all documents. Check console for details.');
    }
}

