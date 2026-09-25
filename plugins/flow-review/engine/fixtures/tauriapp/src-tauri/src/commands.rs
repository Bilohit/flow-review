use serde::Serialize;

#[derive(Serialize)]
pub struct Item {
    pub id: u32,
    pub label: String,
}

#[tauri::command]
pub fn load_items() -> Vec<Item> {
    vec![
        Item { id: 1, label: "First item".into() },
        Item { id: 2, label: "Second item".into() },
    ]
}

// Planted bug (A-36): save_note always fails server-side. The frontend swallows the
// rejection into console.error with no UI feedback -- the user sees nothing happen.
#[tauri::command]
pub fn save_note(_text: String) -> Result<(), String> {
    Err("note store unavailable".into())
}
