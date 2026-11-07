# BEGIN ALVIDAA_NATIVE_WEB_FEED_V1
  echo "--- native Free My TV feed worker ---"
  if [ -x /var/local/alvidaa/native-web-v3/native-image ] && [ -f /var/local/alvidaa/native-web-v3/native-web-service.cjs ]; then
      LD_LIBRARY_PATH=/lib:/usr/local/lib:/basic/lib /opt/pkgs/tv.vidaa.app.phoenix/bin/phoenix \
          /var/local/alvidaa/native-web-v3/native-web-service.cjs start ||
          echo "Native feed worker unavailable; cached Home remains usable"
  fi
  # END ALVIDAA_NATIVE_WEB_FEED_V1
