"""Voice fingerprints: tells your friends apart in a voice call. Runs on this PC with a small speaker-recognition model."""
import threading
import urllib.request
from pathlib import Path

import numpy as np

MODEL = Path(__file__).with_name("models") / "wespeaker_en_voxceleb_resnet34_LM.onnx"
MODEL_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/" + MODEL.name  # sic: their tag
MATCH = 0.5  # cosine similarity needed to call two clips the same voice
MARGIN = 0.05  # and the best match has to beat the runner-up by this much


class Voices:
    def __init__(self):
        self._extractor = None
        self._lock = threading.Lock()

    def _model(self):
        with self._lock:
            if self._extractor is None:
                import sherpa_onnx
                if not MODEL.exists():  # first use: 26.5 MB, once
                    MODEL.parent.mkdir(exist_ok=True)
                    tmp = MODEL.with_suffix(".part")
                    urllib.request.urlretrieve(MODEL_URL, tmp)
                    tmp.replace(MODEL)
                self._extractor = sherpa_onnx.SpeakerEmbeddingExtractor(
                    sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(MODEL), num_threads=2))
            return self._extractor

    def fingerprint(self, audio):
        """A unit-length voice fingerprint for 16 kHz mono float audio."""
        ex = self._model()
        stream = ex.create_stream()
        stream.accept_waveform(16000, np.ascontiguousarray(audio, dtype=np.float32))
        stream.input_finished()
        v = np.array(ex.compute(stream), dtype=np.float32)
        return v / (np.linalg.norm(v) or 1.0)


def identify(prints, fp):
    """(name, similarity) of the known voice that matches fingerprint fp, or (None, best similarity)."""
    scores = sorted(((float(np.dot(fp, np.array(v, dtype=np.float32))), name) for name, v in prints.items()), reverse=True)
    if not scores:
        return None, 0.0
    best, name = scores[0]
    runner_up = scores[1][0] if len(scores) > 1 else -1.0
    return (name if best >= MATCH and best - runner_up >= MARGIN else None), best


def learn(old, fp, weight=1.0):
    """Blend a new clip into a stored fingerprint (weight 1 = replace); returns a plain list for memory.json."""
    v = fp if old is None else (1 - weight) * np.array(old, dtype=np.float32) + weight * fp
    return [round(float(x), 5) for x in v / (np.linalg.norm(v) or 1.0)]
