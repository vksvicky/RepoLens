#!/bin/bash
# Notarize build using Apple ID password from env.
export APPLE_ID_PASSWORD="$NOTARIZE_PASSWORD"
xcrun notarytool submit dist/App.zip --apple-id "$APPLE_ID" --password "$APPLE_ID_PASSWORD"
