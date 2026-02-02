-- Add rich-text case description for image stack (TinyMCE HTML)
ALTER TABLE case_image_stack ADD COLUMN IF NOT EXISTS description_html TEXT;
