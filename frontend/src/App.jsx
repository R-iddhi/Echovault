import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { AnimatePresence, motion } from "framer-motion";

import {
  Archive,
  AudioLines,
  Check,
  ChevronRight,
  FileText,
  Lightbulb,
  LockKeyhole,
  MapPin,
  Mic2,
  Search,
  Sparkles,
  Trash2,
  Upload,
  Users,
} from "lucide-react";

import "./cinematic.css";
import "./fullscreen-scenes.css";

const API_BASE = "http://127.0.0.1:8000";
const VAULT_KEY = "echovault_memories";

const sampleMemory = `Every Diwali, my mother would wake us before sunrise.

She made karanji the night before, but nobody was allowed to touch them until after the puja.

My brother always tried to steal one from the kitchen.

In 1992, after we moved to Pune, that became our first Diwali away from Ratnagiri.

She said the house felt different, but making the same food made it feel like home again.`;

const processingMessages = [
  "Listening to what remains...",
  "Finding people and places...",
  "Tracing meaningful moments...",
  "Checking the preserved source...",
  "Preparing the memory...",
];

function App() {
  const [stage, setStage] = useState("home");

  const [story, setStory] = useState("");
  const [memoryData, setMemoryData] = useState(null);

  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);

  const [audioFile, setAudioFile] = useState(null);
  const [audioUrl, setAudioUrl] = useState("");
  const [hints, setHints] = useState("");

  const [transcribing, setTranscribing] = useState(false);
  const [transcriptionInfo, setTranscriptionInfo] = useState(null);

  const [loading, setLoading] = useState(false);
  const [loadingIndex, setLoadingIndex] = useState(0);

  const [asking, setAsking] = useState(false);
  const [error, setError] = useState("");

  const [selectedEvidence, setSelectedEvidence] = useState(null);

  const [savedMemories, setSavedMemories] = useState([]);

  const [introVisible, setIntroVisible] = useState(true);

  const [pointer, setPointer] = useState({
    x: 0,
    y: 0,
  });

  const [pumpkinBurst, setPumpkinBurst] = useState(false);
  const [transitionFlash, setTransitionFlash] = useState(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(VAULT_KEY);

      if (saved) {
        setSavedMemories(JSON.parse(saved));
      }
    } catch {
      setSavedMemories([]);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIntroVisible(false);
    }, 3600);

    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!loading) {
      setLoadingIndex(0);
      return;
    }

    const timer = setInterval(() => {
      setLoadingIndex(
        (current) => (current + 1) % processingMessages.length
      );
    }, 1700);

    return () => clearInterval(timer);
  }, [loading]);

  useEffect(() => {
    return () => {
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
    };
  }, [audioUrl]);

  const archiveTitle = useMemo(() => {
    return (
      memoryData?.title ||
      memoryData?.moments?.[0]?.title ||
      "A Memory Worth Keeping"
    );
  }, [memoryData]);

  const saveMemories = (memories) => {
    setSavedMemories(memories);
    localStorage.setItem(VAULT_KEY, JSON.stringify(memories));
  };

  const clearWorkingMemory = () => {
    setStory("");
    setMemoryData(null);
    setQuestion("");
    setAnswer(null);
    setAudioFile(null);

    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
    }

    setAudioUrl("");
    setHints("");
    setTranscriptionInfo(null);
    setError("");
    setSelectedEvidence(null);
  };

  const runPageTransition = (callback) => {
    setPumpkinBurst(false);
    setTransitionFlash(false);

    requestAnimationFrame(() => {
      setPumpkinBurst(true);
      setTransitionFlash(true);
    });

    setTimeout(() => {
      callback();
    }, 430);

    setTimeout(() => {
      setTransitionFlash(false);
    }, 820);

    setTimeout(() => {
      setPumpkinBurst(false);
    }, 1100);
  };

  const goHome = () => {
    runPageTransition(() => {
      clearWorkingMemory();
      setStage("home");
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  };

  const startNewMemory = () => {
    runPageTransition(() => {
      clearWorkingMemory();
      setStage("preserve");
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  };

  const openDemo = () => {
    runPageTransition(() => {
      clearWorkingMemory();
      setStory(sampleMemory);
      setStage("preserve");
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  };

  const openVault = () => {
    runPageTransition(() => {
      setStage("vault");
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  };

  const handleAudioChange = (event) => {
    const file = event.target.files?.[0];

    if (!file) return;

    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
    }

    setAudioFile(file);
    setAudioUrl(URL.createObjectURL(file));
    setTranscriptionInfo(null);
    setError("");
  };

  const transcribeAudio = async () => {
    if (!audioFile) return;

    setTranscribing(true);
    setError("");

    try {
      const formData = new FormData();

      formData.append("file", audioFile);
      formData.append("hints", hints);

      const response = await axios.post(
        `${API_BASE}/transcribe-audio`,
        formData
      );

      setStory(response.data.transcript);

      setTranscriptionInfo({
        language: response.data.language,
        probability: response.data.language_probability,
      });
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "The recording could not be transcribed."
      );
    } finally {
      setTranscribing(false);
    }
  };

  const preserveMemory = async () => {
    if (!story.trim()) return;

    setLoading(true);
    setError("");
    setAnswer(null);
    setSelectedEvidence(null);

    try {
      const response = await axios.post(`${API_BASE}/extract-memory`, {
        story,
      });

      const result = response.data;

      setMemoryData(result);

      const memory = {
        id: Date.now(),
        title:
          result?.title ||
          result?.moments?.[0]?.title ||
          "A Memory Worth Keeping",
        story,
        memoryData: result,
        savedAt: new Date().toISOString(),
      };

      saveMemories([memory, ...savedMemories]);

      setStage("archive");

      window.scrollTo({
        top: 0,
        behavior: "smooth",
      });

      setPumpkinBurst(true);

      setTimeout(() => {
        setPumpkinBurst(false);
      }, 1000);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "This memory could not be preserved."
      );
    } finally {
      setLoading(false);
    }
  };

  const askMemory = async () => {
    if (!question.trim() || !story.trim()) return;

    setAsking(true);
    setError("");
    setAnswer(null);

    try {
      const response = await axios.post(`${API_BASE}/ask-memory`, {
        story,
        question,
      });

      setAnswer(response.data);

      if (response.data?.evidence) {
        setSelectedEvidence({
          label: "Supporting source",
          text: response.data.evidence,
        });
      }
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "The memory could not answer that question."
      );
    } finally {
      setAsking(false);
    }
  };

  const reopenMemory = (memory) => {
    runPageTransition(() => {
      setStory(memory.story);
      setMemoryData(memory.memoryData);
      setQuestion("");
      setAnswer(null);
      setSelectedEvidence(null);
      setError("");
      setStage("archive");

      window.scrollTo({
        top: 0,
        behavior: "smooth",
      });
    });
  };

  const deleteMemory = (id) => {
    saveMemories(
      savedMemories.filter((memory) => memory.id !== id)
    );
  };

  const openEvidence = (label, evidence) => {
    if (!evidence) return;

    setSelectedEvidence({
      label,
      text: evidence,
    });
  };

  const safeText = (item) => {
    if (typeof item === "string") {
      return item;
    }

    return item?.name || item?.title || String(item);
  };

  const evidenceForItem = (item) => {
    if (typeof item === "object" && item?.evidence) {
      return item.evidence;
    }

    return story;
  };

  const handlePointerMove = (event) => {
    setPointer({
      x: (event.clientX / window.innerWidth - 0.5) * 2,
      y: (event.clientY / window.innerHeight - 0.5) * 2,
    });
  };

  return (
    <div className={`ev-app stage-${stage}`} onMouseMove={handlePointerMove}>
      {/* FALLING PUMPKINS */}

      <AnimatePresence>
        {pumpkinBurst && (
          <motion.div className="pumpkin-rain">
            {[0, 1, 2, 3, 4].map((pumpkin, index) => (
              <motion.div
                key={pumpkin}
                className={`falling-scary-pumpkin pumpkin-drop-${index + 1}`}
                initial={{
                  y: -220,
                  rotate: -25 + index * 23,
                  opacity: 0,
                }}
                animate={{
                  y: "115vh",
                  rotate: 320 + index * 75,
                  opacity: [0, 1, 1, 0.9, 0],
                }}
                transition={{
                  duration: 0.85 + index * 0.08,
                  delay: index * 0.04,
                  ease: "easeIn",
                }}
              >
                <img src="/pumpkin-glow.png" alt="" />
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      <div
        className={`transition-flash ${
          transitionFlash ? "active" : ""
        }`}
      />

      {/* GLOBAL HAUNTED WORLD */}

      <div className="global-haunted-world">
        <div className="global-house" />
        <div className="global-moon" />
        <div className="global-fog global-fog-a" />
        <div className="global-fog global-fog-b" />

        <div className="global-bats">
          <i />
          <i />
          <i />
        </div>
      </div>

      {/* PAGE-SPECIFIC CREATURES */}

      {stage === "preserve" && (
        <>
          <div className="ghost ghost-one">
            <div className="ghost-head" />
            <div className="ghost-body" />
          </div>

          <div className="floating-candle candle-one">
            <span />
          </div>

          <div className="floating-candle candle-two">
            <span />
          </div>
        </>
      )}

      {stage === "vault" && (
        <>
          <div className="ghost ghost-two">
            <div className="ghost-head" />
            <div className="ghost-body" />
          </div>

          <div className="walking-skeleton">
            <div className="skull" />
            <div className="spine" />
            <div className="arm left-arm" />
            <div className="arm right-arm" />
            <div className="leg left-leg" />
            <div className="leg right-leg" />
          </div>
        </>
      )}

      {stage === "archive" && (
        <div className="skeleton-assembly">
          <div className="bone bone-skull" />
          <div className="bone bone-spine" />
          <div className="bone bone-arm-a" />
          <div className="bone bone-arm-b" />
          <div className="bone bone-leg-a" />
          <div className="bone bone-leg-b" />
        </div>
      )}

      {/* INTRO */}

      <AnimatePresence>
        {introVisible && (
          <motion.div
            className="ev-intro"
            initial={{ opacity: 1 }}
            exit={{
              opacity: 0,
              scale: 1.03,
              filter: "blur(10px)",
            }}
            transition={{ duration: 0.8 }}
            onClick={() => setIntroVisible(false)}
          >
            <motion.div
              className="intro-village"
              initial={{ scale: 1.12 }}
              animate={{ scale: 1 }}
              transition={{ duration: 4 }}
            />

            <div className="intro-vignette" />

            <div className="intro-copy">
              <motion.p
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
              >
                SOME STORIES SHOULD NEVER DISAPPEAR.
              </motion.p>

              <motion.h1
                initial={{
                  opacity: 0,
                  y: 35,
                  filter: "blur(14px)",
                }}
                animate={{
                  opacity: 1,
                  y: 0,
                  filter: "blur(0px)",
                }}
                transition={{
                  delay: 0.8,
                  duration: 1,
                }}
              >
                EchoVault
              </motion.h1>

              <motion.h2
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 1.45 }}
              >
                Some memories refuse to disappear.
              </motion.h2>

              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 0.75 }}
                transition={{ delay: 2.1 }}
              >
                click anywhere to enter
              </motion.span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* NAV */}

      <header className="ev-nav">
        <button className="ev-brand" onClick={goHome}>
          <span className="brand-mark">
            <Archive size={18} />
          </span>

          <span>
            <strong>EchoVault</strong>
            <small>Memory archive</small>
          </span>
        </button>

        <nav>
          <button onClick={openVault}>My Vault</button>

          <button className="nav-cta" onClick={startNewMemory}>
            Preserve
          </button>
        </nav>
      </header>

      <AnimatePresence mode="wait">
        {/* HOME */}

        {stage === "home" && (
          <motion.main
            key="home"
            className="ev-home"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <section className="ev-hero">
              <motion.div
                className="hero-panel"
                initial={{ opacity: 0, x: -30 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.7 }}
              >
                <div className="eyebrow">
                  <span />
                  GHOST IN THE MACHINE
                </div>

                <h1>
                  Some memories
                  <span>refuse to disappear.</span>
                </h1>

                <p>
                  Preserve the voices, stories and traditions your family
                  leaves behind.
                </p>

                <div className="hero-actions">
                  <button className="primary-btn" onClick={startNewMemory}>
                    Preserve a memory
                    <ChevronRight size={17} />
                  </button>

                  <button className="secondary-btn" onClick={openDemo}>
                    <Sparkles size={15} />
                    Explore a memory
                  </button>
                </div>
              </motion.div>

              <motion.div
                className="haunted-world"
                style={{
                  transform: `perspective(1200px)
                    rotateY(${pointer.x * 2}deg)
                    rotateX(${pointer.y * -1.4}deg)`,
                }}
              >
                <div className="world-village" />
                <div className="world-pumpkins" />
                <div className="world-vignette" />
                <div className="moon-glow" />
                <div className="orange-glow" />

                <div className="memory-ui voice-card">
                  <div className="ui-label">
                    <AudioLines size={14} />
                    ORIGINAL VOICE
                  </div>

                  <div className="wave-row">
                    {Array.from({ length: 16 }).map((_, i) => (
                      <i
                        key={i}
                        style={{
                          animationDelay: `${i * 0.06}s`,
                        }}
                      />
                    ))}
                  </div>

                  <small>A voice worth keeping.</small>
                </div>

                <div className="memory-ui evidence-card">
                  <div className="ui-label">
                    <Lightbulb size={14} />
                    GHOSTLIGHT
                  </div>

                  <strong>Source found</strong>

                  <small>
                    Every recovered moment can lead back to the original story.
                  </small>
                </div>

                <div className="scene-copy">
                  <strong>Nothing invented.</strong>
                  <small>The original memory stays at the centre.</small>
                </div>
              </motion.div>
            </section>

            <section className="ev-principles">
              <article>
                <span>01</span>
                <Mic2 />
                <h3>Keep the voice</h3>
                <p>Begin with a real recording or written family story.</p>
              </article>

              <article>
                <span>02</span>
                <Sparkles />
                <h3>Recover the story</h3>
                <p>
                  Find the people, places, traditions and important moments.
                </p>
              </article>

              <article>
                <span>03</span>
                <Lightbulb />
                <h3>Turn on Ghostlight</h3>
                <p>
                  Trace recovered details back to the original preserved words.
                </p>
              </article>
            </section>
          </motion.main>
        )}

        {/* PRESERVE */}

        {stage === "preserve" && (
          <motion.main
            key="preserve"
            className="ev-page preserve-page"
            initial={{ opacity: 0, x: 24 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0 }}
          >
            <div className="page-intro">
              <div className="eyebrow">
                <span />
                PRESERVE A MEMORY
              </div>

              <h1>
                Give a memory
                <span>somewhere safe to stay.</span>
              </h1>

              <p>
                Add a recording, review what was said and preserve the story.
              </p>
            </div>

            <div className="preserve-layout">
              <section className="glass-panel recording-panel">
                <div className="panel-header">
                  <div>
                    <span>RECORDING</span>
                    <h2>Add a voice</h2>
                  </div>

                  <Mic2 size={21} />
                </div>

                <label className="upload-zone">
                  <input
                    type="file"
                    accept="audio/*,.mp4,.webm"
                    onChange={handleAudioChange}
                  />

                  <div className="upload-icon">
                    <Upload size={21} />
                  </div>

                  <strong>Choose a recording</strong>
                  <p>or drop an audio file here</p>
                  <small>MP3 · WAV · M4A · WEBM · OGG</small>
                </label>

                {audioFile && (
                  <div className="audio-card">
                    <div className="audio-meta">
                      <span className="record-dot" />

                      <div>
                        <strong>{audioFile.name}</strong>

                        <small>
                          {(audioFile.size / 1024 / 1024).toFixed(2)} MB
                        </small>
                      </div>
                    </div>

                    {audioUrl && <audio controls src={audioUrl} />}

                    <div className="hint-field">
                      <label>
                        Names or places
                        <small>
                          Optional — helps with unusual names and regional words.
                        </small>
                      </label>

                      <input
                        value={hints}
                        onChange={(e) => setHints(e.target.value)}
                        placeholder="Aaji, Riddhi, Pune, Ratnagiri..."
                      />
                    </div>

                    <button
                      className="primary-btn full-width"
                      onClick={transcribeAudio}
                      disabled={transcribing}
                    >
                      {transcribing ? (
                        <>
                          <AudioLines size={16} />
                          Listening...
                        </>
                      ) : (
                        <>
                          <Mic2 size={16} />
                          Transcribe recording
                        </>
                      )}
                    </button>
                  </div>
                )}

                {transcribing && (
                  <div className="live-listening">
                    <div className="live-wave">
                      {Array.from({ length: 30 }).map((_, i) => (
                        <i
                          key={i}
                          style={{
                            animationDelay: `${i * 0.045}s`,
                          }}
                        />
                      ))}
                    </div>

                    <div>
                      <strong>Listening to your memory...</strong>
                      <p>The transcript will appear as soon as it is ready.</p>
                    </div>
                  </div>
                )}

                {transcriptionInfo && (
                  <div className="success-strip">
                    <Check size={16} />
                    Transcript ready. Review it before preserving.
                  </div>
                )}
              </section>

              <section className="glass-panel transcript-panel">
                <div className="panel-header">
                  <div>
                    <span>TRANSCRIPT</span>
                    <h2>Review the memory</h2>
                  </div>

                  <FileText size={21} />
                </div>

                <div className="editor-shell">
                  <span className="editor-label">WHAT WAS SAID</span>

                  <textarea
                    value={story}
                    onChange={(e) => setStory(e.target.value)}
                    placeholder="Your transcript will appear here. You can also type or paste a memory."
                  />

                  <div className="editor-footer">
                    <span>{story.length} characters</span>

                    <button onClick={openDemo}>Use sample memory</button>
                  </div>
                </div>

                {error && <div className="error-strip">{error}</div>}

                <button
                  className="seal-btn"
                  onClick={preserveMemory}
                  disabled={!story.trim() || loading}
                >
                  <span>
                    <LockKeyhole size={17} />
                    Preserve this memory
                  </span>

                  <ChevronRight size={18} />
                </button>
              </section>
            </div>
          </motion.main>
        )}

        {/* VAULT */}

        {stage === "vault" && (
          <motion.main
            key="vault"
            className="ev-page vault-page"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <div className="page-intro">
              <div className="eyebrow">
                <span />
                YOUR ARCHIVE
              </div>

              <h1>
                Your
                <span>Vault.</span>
              </h1>

              <p>Voices and stories you chose to keep.</p>

              <button className="primary-btn" onClick={startNewMemory}>
                Preserve another memory
                <ChevronRight size={16} />
              </button>
            </div>

            {savedMemories.length === 0 ? (
              <div className="empty-state">
                <Archive size={35} />

                <h2>The vault is empty.</h2>

                <p>
                  Preserve your first voice or story to begin building your
                  archive.
                </p>

                <button className="primary-btn" onClick={startNewMemory}>
                  Preserve first memory
                </button>
              </div>
            ) : (
              <div className="vault-grid">
                {savedMemories.map((memory, index) => (
                  <motion.article
                    className="archive-card"
                    key={memory.id}
                    initial={{ opacity: 0, y: 18 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                    whileHover={{ y: -5 }}
                  >
                    <div className="archive-card-top">
                      <span>
                        MEMORY {String(index + 1).padStart(2, "0")}
                      </span>

                      <small>
                        {new Date(memory.savedAt).toLocaleDateString()}
                      </small>
                    </div>

                    <h2>{memory.title}</h2>

                    <p>
                      {memory.story.length > 170
                        ? `${memory.story.slice(0, 170)}...`
                        : memory.story}
                    </p>

                    <div className="archive-card-tags">
                      {memory.memoryData?.people
                        ?.slice(0, 2)
                        .map((item, i) => (
                          <span key={`p-${i}`}>
                            <Users size={11} />
                            {safeText(item)}
                          </span>
                        ))}

                      {memory.memoryData?.places
                        ?.slice(0, 2)
                        .map((item, i) => (
                          <span key={`pl-${i}`}>
                            <MapPin size={11} />
                            {safeText(item)}
                          </span>
                        ))}
                    </div>

                    <div className="archive-card-actions">
                      <button onClick={() => reopenMemory(memory)}>
                        Open memory
                        <ChevronRight size={14} />
                      </button>

                      <button
                        className="danger-button"
                        onClick={() => deleteMemory(memory.id)}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </motion.article>
                ))}
              </div>
            )}
          </motion.main>
        )}

        {/* MEMORY */}

        {stage === "archive" && memoryData && (
          <motion.main
            key="archive"
            className="ev-page archive-page"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <div className="archive-title-row">
              <div className="page-intro">
                <div className="eyebrow">
                  <span />
                  PRESERVED MEMORY
                </div>

                <h1>{archiveTitle}</h1>

                <p>
                  Explore the people, places and moments inside this story.
                </p>
              </div>

              <button
                className="secondary-btn compact"
                onClick={openVault}
              >
                <Archive size={15} />
                My Vault
              </button>
            </div>

            <div className="archive-main-grid">
              <section className="glass-panel memory-map-panel">
                <div className="panel-header">
                  <div>
                    <span>MEMORY MAP</span>
                    <h2>Inside this story</h2>
                  </div>
                </div>

                <div className="memory-map-grid">
                  <MemoryGroup
                    title="People"
                    icon={<Users size={15} />}
                    items={memoryData.people}
                    onSelect={(item) =>
                      openEvidence(
                        `Person · ${safeText(item)}`,
                        evidenceForItem(item)
                      )
                    }
                    safeText={safeText}
                  />

                  <MemoryGroup
                    title="Places"
                    icon={<MapPin size={15} />}
                    items={memoryData.places}
                    onSelect={(item) =>
                      openEvidence(
                        `Place · ${safeText(item)}`,
                        evidenceForItem(item)
                      )
                    }
                    safeText={safeText}
                  />

                  <MemoryGroup
                    title="Traditions"
                    icon={<Sparkles size={15} />}
                    items={memoryData.traditions}
                    onSelect={(item) =>
                      openEvidence(
                        `Tradition · ${safeText(item)}`,
                        evidenceForItem(item)
                      )
                    }
                    safeText={safeText}
                  />
                </div>
              </section>

              <motion.aside
                className={`ghostlight-card ${
                  selectedEvidence ? "ghostlight-active" : ""
                }`}
              >
                <div className="ghostlight-top">
                  <span className="flashlight-icon">
                    <Lightbulb size={18} />
                  </span>

                  <div>
                    <small>GHOSTLIGHT</small>
                    <h2>Source evidence</h2>
                  </div>
                </div>

                {selectedEvidence ? (
                  <motion.div
                    className="evidence-content"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                  >
                    <span>{selectedEvidence.label}</span>

                    <blockquote>
                      “{selectedEvidence.text}”
                    </blockquote>

                    <div className="verified-badge">
                      <Check size={13} />
                      Found in the preserved memory
                    </div>
                  </motion.div>
                ) : (
                  <div className="ghostlight-empty">
                    <Search size={23} />

                    <p>
                      Select a person, place, tradition or recovered moment to
                      reveal its source.
                    </p>
                  </div>
                )}

                <div className="ghostlight-beam" />
              </motion.aside>
            </div>

            <section className="moments-area">
              <div className="section-title">
                <span>RECOVERED MOMENTS</span>
                <h2>Pieces of the story.</h2>
              </div>

              <div className="moments-grid">
                {memoryData.moments?.length ? (
                  memoryData.moments.map((moment, index) => (
                    <motion.button
                      className="moment-card"
                      key={index}
                      whileHover={{ y: -5 }}
                      onClick={() =>
                        openEvidence(
                          moment.title,
                          moment.evidence || moment.text
                        )
                      }
                    >
                      <div className="moment-number">
                        {String(index + 1).padStart(2, "0")}
                      </div>

                      {moment.year && <small>{moment.year}</small>}

                      <h3>{moment.title}</h3>

                      <p>{moment.text}</p>

                      <span>
                        Turn on Ghostlight
                        <ChevronRight size={13} />
                      </span>
                    </motion.button>
                  ))
                ) : (
                  <p className="muted-copy">
                    No recovered moments were found.
                  </p>
                )}
              </div>
            </section>

            <section className="ask-vault-section">
              <div className="ask-copy">
                <span>ASK THIS MEMORY</span>

                <h2>
                  Ask the story.
                  <br />
                  Keep the source.
                </h2>

                <p>
                  Ask something about this preserved memory. If the detail is
                  not present, EchoVault should not invent it.
                </p>
              </div>

              <div className="ask-card">
                <div className="ask-input-row">
                  <Search size={17} />

                  <input
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    placeholder="What happened after they moved to Pune?"
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !asking) {
                        askMemory();
                      }
                    }}
                  />

                  <button
                    onClick={askMemory}
                    disabled={!question.trim() || asking}
                  >
                    {asking ? "Searching..." : "Ask"}
                  </button>
                </div>

                {asking && (
                  <div className="vault-searching">
                    <div className="search-progress" />
                    Searching the preserved story...
                  </div>
                )}

                {answer && (
                  <motion.div
                    className={`vault-answer ${
                      answer.grounded ? "grounded" : "refused"
                    }`}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                  >
                    <span>
                      {answer.grounded
                        ? "SOURCE FOUND"
                        : "DETAIL NOT FOUND"}
                    </span>

                    <h3>{answer.answer}</h3>

                    {answer.evidence && (
                      <button
                        onClick={() =>
                          openEvidence(
                            "Supporting source",
                            answer.evidence
                          )
                        }
                      >
                        View source
                        <ChevronRight size={13} />
                      </button>
                    )}
                  </motion.div>
                )}

                {error && <div className="error-strip">{error}</div>}
              </div>
            </section>

            <section className="original-transcript-section">
              <div className="section-title">
                <span>ORIGINAL MEMORY</span>
                <h2>What was actually said.</h2>
              </div>

              <div className="original-transcript">{story}</div>
            </section>
          </motion.main>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {loading && (
          <motion.div
            className="processing-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <div className="processing-glow" />

            <div className="processing-content">
              <div className="processing-mark">
                <Archive size={25} />
                <span />
              </div>

              <small>PRESERVING MEMORY</small>

              <AnimatePresence mode="wait">
                <motion.h2
                  key={loadingIndex}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                >
                  {processingMessages[loadingIndex]}
                </motion.h2>
              </AnimatePresence>

              <p>The original words remain unchanged.</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <footer className="ev-footer">
        <span>ECHOVAULT</span>
        <p>Keep the memory. Keep the evidence.</p>
        <small>Your stories stay yours.</small>
      </footer>
    </div>
  );
}

function MemoryGroup({
  title,
  icon,
  items,
  onSelect,
  safeText,
}) {
  return (
    <div className="memory-group">
      <div className="memory-group-title">
        {icon}
        <span>{title}</span>
      </div>

      {items?.length ? (
        items.map((item, index) => (
          <button
            key={index}
            onClick={() => onSelect(item)}
          >
            {safeText(item)}
          </button>
        ))
      ) : (
        <p>Nothing found.</p>
      )}
    </div>
  );
}

export default App;

