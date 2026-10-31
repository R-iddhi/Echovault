EchoVault Fullscreen Scenes Patch

Files included:
public\haunted-mansion.png
public\vault-skeleton-scene.png
src\fullscreen-scenes.css

IMPORTANT:
Add this line immediately after import "./cinematic.css"; in src\App.jsx:

import "./fullscreen-scenes.css";

The new stylesheet is an override, so your existing cinematic.css remains untouched.

Visual result:
- Home: haunted village full screen
- Preserve: haunted mansion full screen
- Vault: user skeleton artwork full screen + animated walking skeleton
- Memory: haunted mansion full screen + falling/assembling skeleton bones
- Existing pumpkin rain remains
