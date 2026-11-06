/*
 * probe_alsa_capture.c — does the TV's capture PCM carry the final mix?
 *
 * The question this answers: /dev/snd/pcmC0D0c exists and reports
 * "capture 1", but does a read from it give you what the room hears
 * (post-DSP, post-volume), or the decoder output before the TV's own
 * processing? If it is the latter, streaming the TV's audio to other
 * rooms will not match the speakers and the snapcast idea is much less
 * useful.
 *
 * Deliberately links against the TV's own /vendor/lib/libasound.so.2
 * rather than a static build: the lib is already there, and a dynamic
 * armhf binary is a tenth of the work of statically linking ALSA.
 *
 * No headers: alsa-lib is not on the TV, so the handful of symbols we
 * need are declared here. The ABI is stable and these four calls have
 * not changed in a decade.
 *
 * Usage: probe_alsa_capture [device] [outfile] [seconds]
 *   device   default hw:0,0     (pcmC0D0c)
 *   outfile  default /tmp/cap.raw  (S16_LE, 48k, stereo)
 *   seconds  default 2
 *
 * Exit: 0 captured, 1 open/param/read failure. Prints peak/RMS so a
 * silent device is obvious without pulling the file back.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

/* --- minimal alsa-lib ABI ------------------------------------------- */
typedef struct _snd_pcm snd_pcm_t;

enum {
    SND_PCM_STREAM_CAPTURE = 1,
    SND_PCM_FORMAT_S16_LE = 2,
    SND_PCM_ACCESS_RW_INTERLEAVED = 3,
};

extern int snd_pcm_open(snd_pcm_t **pcm, const char *name, int stream, int mode);
extern int snd_pcm_set_params(snd_pcm_t *pcm, int format, int access,
                              unsigned int channels, unsigned int rate,
                              int soft_resample, unsigned int latency);
extern long snd_pcm_readi(snd_pcm_t *pcm, void *buf, unsigned long size);
extern int snd_pcm_start(snd_pcm_t *pcm);
extern int snd_pcm_recover(snd_pcm_t *pcm, int err, int silent);
extern int snd_pcm_close(snd_pcm_t *pcm);
extern const char *snd_strerror(int errnum);

#define RATE 48000
#define CHANNELS 2
#define FRAMES 1024

int main(int argc, char **argv) {
    const char *dev = argc > 1 ? argv[1] : "hw:0,0";
    const char *out = argc > 2 ? argv[2] : "/tmp/cap.raw";
    int seconds = argc > 3 ? atoi(argv[3]) : 2;

    if (seconds <= 0) seconds = 2;

    snd_pcm_t *pcm = NULL;
    int rc = snd_pcm_open(&pcm, dev, SND_PCM_STREAM_CAPTURE, 0);
    if (rc < 0) {
        fprintf(stderr, "open %s: %s\n", dev, snd_strerror(rc));
        return 1;
    }

    rc = snd_pcm_set_params(pcm, SND_PCM_FORMAT_S16_LE,
                            SND_PCM_ACCESS_RW_INTERLEAVED,
                            CHANNELS, RATE, 1, 200000);
    if (rc < 0) {
        fprintf(stderr, "set_params: %s\n", snd_strerror(rc));
        snd_pcm_close(pcm);
        return 1;
    }

    /* Some drivers need the capture stream started explicitly; readi()
       starts it implicitly on most, but this one returned EIO without it. */
    rc = snd_pcm_start(pcm);
    if (rc < 0) {
        fprintf(stderr, "start: %s (continuing, readi may start it)\n",
                snd_strerror(rc));
    }

    FILE *f = fopen(out, "wb");
    if (!f) {
        perror("fopen");
        snd_pcm_close(pcm);
        return 1;
    }

    int16_t buf[FRAMES * CHANNELS];
    long total_frames = (long)RATE * seconds;
    long got = 0;
    int64_t peak = 0;
    double sumsq = 0.0;
    long samples = 0;

    while (got < total_frames) {
        long n = snd_pcm_readi(pcm, buf, FRAMES);
        if (n < 0) {
            /* EIO/EPIPE on capture usually means the stream needs
               re-preparing rather than that the device is dead. */
            rc = snd_pcm_recover(pcm, (int)n, 1);
            fprintf(stderr, "readi: %s (recover rc=%d)\n",
                    snd_strerror((int)n), rc);
            if (rc < 0) break;
            continue;
        }
        fwrite(buf, sizeof(int16_t), (size_t)n * CHANNELS, f);
        for (long i = 0; i < n * CHANNELS; i++) {
            int64_t v = buf[i];
            if (v < 0) v = -v;
            if (v > peak) peak = v;
            sumsq += (double)buf[i] * (double)buf[i];
            samples++;
        }
        got += n;
    }

    fclose(f);
    snd_pcm_close(pcm);

    double rms = samples ? __builtin_sqrt(sumsq / (double)samples) : 0.0;
    printf("device=%s frames=%ld seconds=%.2f peak=%lld rms=%.1f out=%s\n",
           dev, got, (double)got / RATE, (long long)peak, rms, out);

    if (got == 0) return 1;
    if (peak == 0) {
        printf("SILENT: capture returned digital silence — either nothing is "
               "playing, or this PCM is not the output mix\n");
    }
    return 0;
}
