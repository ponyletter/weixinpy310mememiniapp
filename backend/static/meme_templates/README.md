# Meme template manifest

`templates.json` is an allowlist of manually reviewed, mostly text-free source images.
The renderer resolves each `source_item_id` through the bundled ChineseBQB catalog,
downloads only from the configured ChineseBQB CDN, and places the image on a new
480 × 480 caption canvas.

The source repository is recorded on every manifest entry. The ChineseBQB media
repository does not currently state a media license, so its images must not be
described as MIT-licensed merely because an integrating client is MIT-licensed.
Review or replace individual sources before commercial redistribution.
