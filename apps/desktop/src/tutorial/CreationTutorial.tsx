import { useId, useLayoutEffect, useRef, useState } from "react";

import { Stepper } from "../components/Stepper";
import {
  advanceTutorial,
  TUTORIAL_MODULES,
  TUTORIAL_REFERENCE_ASSETS,
  TUTORIAL_STEPS,
  TUTORIAL_STORY as story,
  tutorialMedia,
  tutorialReferencesValid,
} from "./tutorialData";
import "./CreationTutorial.css";

interface HighlightRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export function CreationTutorial({ onClose }: { onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const coachRef = useRef<HTMLElement>(null);
  const [index, setIndex] = useState(0);
  const [selectedReferenceIds, setSelectedReferenceIds] = useState<string[]>([]);
  const [highlight, setHighlight] = useState<HighlightRect | null>(null);
  const maskId = useId();
  const step = TUTORIAL_STEPS[index];
  const referencesValid = tutorialReferencesValid(selectedReferenceIds);
  const selectedReferenceNames = TUTORIAL_REFERENCE_ASSETS.filter((asset) =>
    selectedReferenceIds.includes(asset.id),
  )
    .map((asset) => asset.name)
    .join("、");
  const imagesReady =
    index >= TUTORIAL_STEPS.findIndex((item) => item.target === "generate-videos");
  const videosReady =
    index >= TUTORIAL_STEPS.findIndex((item) => item.target === "nav-generation");
  const moduleIndex = TUTORIAL_MODULES.findIndex((module) => module.id === step.module);

  useLayoutEffect(() => {
    const dialog = dialogRef.current!;
    dialog.showModal();
    return () => dialog.close();
  }, []);

  useLayoutEffect(() => {
    const dialog = dialogRef.current!;
    const target = dialog.querySelector<HTMLElement>(
      `[data-tutorial-target="${step.target}"]`,
    );
    if (!target) return;
    target.scrollIntoView({ block: "nearest", inline: "nearest" });
    target.focus({ preventScroll: true });
    const measure = () => {
      const rect = target.getBoundingClientRect();
      const canvas = target.closest(".tutorial-canvas")?.getBoundingClientRect();
      const left = Math.max(rect.left, canvas?.left ?? 0);
      const top = Math.max(rect.top, canvas?.top ?? 0);
      const right = Math.min(rect.right, canvas?.right ?? innerWidth);
      const bottom = Math.min(rect.bottom, canvas?.bottom ?? innerHeight);
      setHighlight({
        x: left,
        y: top,
        width: Math.max(0, right - left),
        height: Math.max(0, bottom - top),
      });
    };
    const frame = requestAnimationFrame(measure);
    const observer = new ResizeObserver(measure);
    observer.observe(target);
    observer.observe(dialog);
    // Images and wrapped text can move the target without resizing the target itself.
    for (
      let parent = target.parentElement;
      parent && parent !== dialog;
      parent = parent.parentElement
    ) {
      observer.observe(parent);
    }
    if (coachRef.current) observer.observe(coachRef.current);
    window.addEventListener("resize", measure);
    dialog.addEventListener("scroll", measure, true);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("resize", measure);
      dialog.removeEventListener("scroll", measure, true);
    };
  }, [step.target]);

  function advance(target: string) {
    setIndex((current) => advanceTutorial(current, target));
  }
  function action(target: string, label: string) {
    return (
      <button
        type="button"
        className="btn-primary"
        data-tutorial-target={target}
        aria-describedby={step.target === target ? "tutorial-instruction" : undefined}
        disabled={step.target !== target}
        onClick={() => advance(target)}
      >
        {label}
      </button>
    );
  }
  function area(target: string) {
    return {
      "data-tutorial-target": target,
      tabIndex: -1,
      "aria-describedby": step.target === target ? "tutorial-instruction" : undefined,
    };
  }

  function content() {
    switch (step.module) {
      case "project":
        return (
          <>
            <div className="tutorial-story-intro">
              <img src={tutorialMedia("shot-4.svg")} alt="林晚与陈叔在雨夜站台并肩守候" />
              <div>
                <p className="tutorial-eyebrow">离线示例 · 20 秒短剧</p>
                <h2>{story.title}</h2>
                <p>{story.bible.synopsis}</p>
                <p className="muted">{story.genre}</p>
                <p className="field-help">
                  小说、设定、插画和无声短片已内置。练习结果只在本次教程中显示。
                </p>
                {index === 0 ? (
                  action("start", "开始免费教程")
                ) : index === 1 ? (
                  action("create-project", "创建示例项目")
                ) : (
                  <p className="tutorial-success" role="status">
                    示例项目已创建，接下来进入「小说」。
                  </p>
                )}
              </div>
            </div>
            <div className="tutorial-route">
              <h3>一部剧，从这里开始</h3>
              <Stepper
                steps={["故事", "设定", "剧本", "资产", "镜头", "短片"]}
                current={1}
                doneSteps={0}
              />
              <p className="muted">
                你负责检查与选择，AI 在实际项目中负责生成。教程先带你认识每一步。
              </p>
            </div>
          </>
        );
      case "novel":
        return (
          <>
            <div className="tutorial-section-head">
              <div>
                <h2>小说工作室</h2>
                <p className="muted">故事原文是后续制作的起点。</p>
              </div>
              {index === 3 && action("import-novel", "导入示例小说")}
            </div>
            {index === 3 ? (
              <div className="tutorial-empty">
                <h3>准备好你的故事</h3>
                <p>本次练习使用《末班灯火》，不需要选择文件或运行 AI 写作。</p>
              </div>
            ) : (
              <article className="tutorial-document" {...area("novel-content")}>
                <p className="tutorial-eyebrow">{story.title} · 已导入</p>
                <h3>{story.chapterTitle}</h3>
                <div className="tutorial-prose">{story.novel}</div>
              </article>
            )}
          </>
        );
      case "bible":
        return (
          <>
            <div className="tutorial-section-head">
              <div>
                <h2>故事圣经</h2>
                <p className="muted">把故事整理成一份共同的设定。</p>
              </div>
              {index === 6 && action("analyze-story", "分析故事（示例）")}
            </div>
            {index === 6 ? (
              <div className="tutorial-empty">
                <h3>分析来源：{story.title}</h3>
                <p>{story.bible.synopsis}</p>
              </div>
            ) : (
              <div className="tutorial-document" {...area("bible-content")}>
                <h3>故事与世界</h3>
                <p>{story.bible.synopsis}</p>
                <p>{story.bible.world}</p>
                <p className="muted">主题：{story.bible.theme}</p>
                <h3>人物</h3>
                {story.bible.characters.map((character) => (
                  <p key={character.name}>
                    <strong>{character.name}</strong> · {character.description}
                  </p>
                ))}
                <h3>地点与道具</h3>
                <p>
                  <strong>{story.bible.location.name}</strong> ·{" "}
                  {story.bible.location.description}
                </p>
                <p>
                  <strong>{story.bible.prop.name}</strong> ·{" "}
                  {story.bible.prop.description}
                </p>
              </div>
            )}
          </>
        );
      case "script":
        return (
          <>
            <div className="tutorial-section-head">
              <div>
                <h2>分集剧本</h2>
                <p className="muted">来源：{story.title} / 第一章</p>
              </div>
              {index === 9 ? (
                action("generate-script", "生成剧本（示例）")
              ) : index === 10 ? (
                action("save-script", "保存剧本（示例）")
              ) : (
                <span className="tutorial-success">已保存</span>
              )}
            </div>
            {index === 9 ? (
              <div className="tutorial-empty">
                <h3>从叙事到场景</h3>
                <p>将人物的想法变成看得见的动作，整理可以说出口的台词。</p>
              </div>
            ) : (
              <article className="tutorial-document">
                <p className="tutorial-eyebrow">
                  {index === 10 ? "生成结果 · 等待审核保存" : "已保存 · 可用于制作分镜"}
                </p>
                <h3>{story.scene.title}</h3>
                <p className="tutorial-slugline">{story.scene.slugline}</p>
                <h4>动作</h4>
                <p>{story.scene.action}</p>
                <h4>对白</h4>
                {story.scene.dialogue.map((line) => (
                  <p className="tutorial-dialogue" key={line}>
                    {line}
                  </p>
                ))}
              </article>
            )}
          </>
        );
      case "assets":
        return (
          <>
            <div className="tutorial-section-head">
              <div>
                <h2>参考资产</h2>
                <p className="muted">人物 / 地点 / 道具 · 同一套视觉设定</p>
              </div>
              {index === 12 && action("generate-assets", "生成参考图（示例）")}
            </div>
            {index === 12 ? (
              <div className="tutorial-empty">
                <h3>先固定外观，再制作镜头</h3>
                <p>林晚与陈叔将反复出现在不同镜头里；青岚站和旧车票也需要保持一致。</p>
              </div>
            ) : (
              <div className="tutorial-art-gallery" {...area("asset-content")}>
                {[...story.bible.characters, story.bible.location, story.bible.prop].map(
                  (asset) => (
                    <figure key={asset.name}>
                      <img
                        src={tutorialMedia(asset.image)}
                        alt={`${asset.name}的预置参考插画`}
                      />
                      <figcaption>
                        <strong>{asset.name}</strong>
                        <p>{asset.description}</p>
                        <small className="muted">示例参考图 · 版本 1</small>
                      </figcaption>
                    </figure>
                  ),
                )}
              </div>
            )}
          </>
        );
      case "storyboard":
        return (
          <>
            <div className="tutorial-section-head">
              <div>
                <h2>场景分镜</h2>
                <p className="muted">{story.scene.slugline} · 4 镜头 / 共 20 秒</p>
              </div>
              {step.target === "generate-shots"
                ? action("generate-shots", "生成分镜（示例）")
                : step.target === "generate-images"
                  ? action("generate-images", "生成分镜图（示例）")
                  : step.target === "generate-videos"
                    ? action("generate-videos", "生成视频（示例）")
                    : null}
            </div>
            {step.target === "generate-shots" ? (
              <div className="tutorial-empty">
                <h3>把场景拆成四个镜头</h3>
                <p>{story.scene.action}</p>
              </div>
            ) : (
              <>
                {step.target === "reference-selection" && (
                  <section
                    className="tutorial-reference-picker"
                    {...area("reference-selection")}
                    aria-labelledby="tutorial-reference-title"
                  >
                    <h3 id="tutorial-reference-title">镜头 1 · 选择参考资产</h3>
                    <p>{story.shots[0].action}</p>
                    <p className="field-help">
                      先练习为镜头 1
                      选参考图，其余镜头已按模板配置。勾选与本镜头有关的资产即可。
                    </p>
                    <div className="tutorial-reference-options">
                      {TUTORIAL_REFERENCE_ASSETS.map((asset) => (
                        <label key={asset.id} className="tutorial-reference-option">
                          <input
                            type="checkbox"
                            aria-label={`使用${asset.label} ${asset.name}作为参考图`}
                            checked={selectedReferenceIds.includes(asset.id)}
                            onChange={(event) =>
                              setSelectedReferenceIds((current) =>
                                event.target.checked
                                  ? [...current, asset.id]
                                  : current.filter((id) => id !== asset.id),
                              )
                            }
                          />
                          <img src={tutorialMedia(asset.image)} alt="" />
                          <span>
                            {asset.label} · {asset.name}
                          </span>
                        </label>
                      ))}
                    </div>
                    <p className="field-help" role="status">
                      {referencesValid
                        ? "选择正确：林晚固定人物外观，青岚站固定场景。"
                        : selectedReferenceIds.some(
                              (id) => id === "chen-shu" || id === "ticket",
                            )
                          ? "陈叔和车票不是这个镜头的参考重点，请取消勾选，并选中林晚和青岚站。"
                          : "请勾选林晚和青岚站，分别保持人物与地点一致。"}
                    </p>
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={!referencesValid}
                      aria-describedby="tutorial-instruction"
                      onClick={() => {
                        if (referencesValid) advance("reference-selection");
                      }}
                    >
                      确认参考资产
                    </button>
                  </section>
                )}
                {videosReady && (
                  <div className="tutorial-clip-preview">
                    <video
                      controls
                      playsInline
                      preload="metadata"
                      poster={tutorialMedia("shot-1.svg")}
                      src={tutorialMedia("shot-1.mp4")}
                      aria-label="第一镜头示例视频"
                    />
                    <p className="field-help">
                      镜头 1 · 5 秒 · 本地预置无声视频，其余三条也已备好。
                    </p>
                  </div>
                )}
                <div className="tutorial-shot-list">
                  {story.shots.map((shot) => (
                    <article key={shot.number} className="tutorial-shot">
                      {imagesReady ? (
                        <img
                          src={tutorialMedia(shot.image)}
                          alt={`镜头 ${shot.number}：${shot.action}`}
                        />
                      ) : (
                        <div className="tutorial-shot-placeholder">待制作关键帧</div>
                      )}
                      <div>
                        <p className="tutorial-eyebrow">
                          镜头 {shot.number} · {shot.type} · 5 秒
                        </p>
                        <h3>{shot.camera}</h3>
                        <p>{shot.action}</p>
                        {shot.dialogue && (
                          <p className="tutorial-dialogue">“{shot.dialogue}”</p>
                        )}
                        <p className="field-help">
                          引用：
                          {shot.number === 1
                            ? selectedReferenceNames || "尚未选择"
                            : shot.references}
                        </p>
                        <details>
                          <summary>查看镜头提示词</summary>
                          <p>{shot.prompt}</p>
                        </details>
                        <p className={videosReady ? "tutorial-success" : "muted"}>
                          {videosReady
                            ? "关键帧与视频已备好"
                            : imagesReady
                              ? "关键帧已备好"
                              : "已规划镜头"}
                        </p>
                      </div>
                    </article>
                  ))}
                </div>
              </>
            )}
          </>
        );
      case "generation":
        return (
          <>
            <div className="tutorial-section-head">
              <div>
                <h2>剧集制作台</h2>
                <p className="muted">{story.scene.title}</p>
              </div>
              {step.target === "prepare-episode" ? (
                action("prepare-episode", "准备本集（示例）")
              ) : step.target === "compose-episode" ? (
                action("compose-episode", "合成本集（示例）")
              ) : (
                <span className="tutorial-success">教程完成</span>
              )}
            </div>
            {step.target === "finished-film" ? (
              <div className="tutorial-finished" {...area("finished-film")}>
                <video
                  controls
                  playsInline
                  preload="metadata"
                  poster={tutorialMedia("shot-4.svg")}
                  src={tutorialMedia("episode.mp4")}
                  aria-label="末班灯火示例短片"
                />
                <p>《{story.title}》 · 20 秒 · 4 个镜头</p>
                <p className="field-help">
                  用本地分镜插画离线制作的无声示例，包含轻微运镜与字幕。真实项目的视频效果由你的模型与提示词决定。
                </p>
              </div>
            ) : (
              <div className="tutorial-production-overview">
                <h3>
                  {step.target === "prepare-episode"
                    ? "检查本集制作条件"
                    : "本集检查通过"}
                </h3>
                <p className="muted">预检查看已有内容，不重新生成，也不覆盖结果。</p>
                <div className="tutorial-table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>镜头</th>
                        <th>剧本与参考</th>
                        <th>关键帧</th>
                        <th>视频</th>
                        <th>结果</th>
                      </tr>
                    </thead>
                    <tbody>
                      {story.shots.map((shot) => (
                        <tr key={shot.number}>
                          <td>
                            {shot.number} · {shot.type}
                          </td>
                          <td>{shot.references}</td>
                          <td>1 张</td>
                          <td>5 秒</td>
                          <td
                            className={
                              step.target === "compose-episode"
                                ? "tutorial-success"
                                : "muted"
                            }
                          >
                            {step.target === "compose-episode" ? "可合成" : "待检查"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {step.target === "compose-episode" && (
                  <p className="tutorial-success" role="status">
                    4 个镜头素材齐全，无缺失项。接下来打开示例合成结果。
                  </p>
                )}
              </div>
            )}
          </>
        );
    }
  }

  return (
    <dialog
      ref={dialogRef}
      className="creation-tutorial"
      aria-labelledby="tutorial-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <header className="tutorial-header">
        <div>
          <h1 id="tutorial-title">新手教程</h1>
          <span className="tutorial-free">免费练习</span>
          <span className="muted">{story.title}</span>
        </div>
        <button type="button" className="tutorial-close" onClick={onClose}>
          退出教程
        </button>
      </header>
      <nav className="tutorial-nav module-nav" aria-label="教程模块导航">
        {TUTORIAL_MODULES.map((module) => (
          <button
            type="button"
            key={module.id}
            data-tutorial-target={`nav-${module.id}`}
            className={step.module === module.id ? "nav-active" : ""}
            aria-current={step.module === module.id ? "step" : undefined}
            aria-describedby={
              step.target === `nav-${module.id}` ? "tutorial-instruction" : undefined
            }
            disabled={step.target !== `nav-${module.id}`}
            onClick={() => advance(`nav-${module.id}`)}
          >
            {module.label}
          </button>
        ))}
      </nav>
      <div className="tutorial-workspace">
        <section className="tutorial-canvas" aria-label="教程练习区">
          {content()}
        </section>
        <aside ref={coachRef} className="tutorial-coach" aria-label="教程指引">
          <div className="tutorial-coach-copy" aria-live="polite" aria-atomic="true">
            <p className="tutorial-eyebrow">
              步骤 {index + 1} / {TUTORIAL_STEPS.length} ·{" "}
              {TUTORIAL_MODULES[moduleIndex].label}
            </p>
            <h2>{step.title}</h2>
            <p id="tutorial-instruction">{step.instruction}</p>
          </div>
          <div className="tutorial-real-use">
            <h3>在自己的项目中</h3>
            <p>{step.realUse}</p>
          </div>
          {step.continueLabel ? (
            <button
              type="button"
              className="btn-primary"
              onClick={() =>
                index === TUTORIAL_STEPS.length - 1 ? onClose() : advance(step.target)
              }
            >
              {step.continueLabel}
            </button>
          ) : (
            <p className="tutorial-click-hint">
              {step.target === "reference-selection"
                ? "在高亮区域勾选资产，再确认选择"
                : "点击高亮区域继续"}
            </p>
          )}
          <div className="tutorial-coach-controls">
            <button
              type="button"
              disabled={index === 0}
              onClick={() => setIndex((current) => Math.max(0, current - 1))}
            >
              上一步
            </button>
            <button
              type="button"
              disabled={index === 0}
              onClick={() => {
                setIndex(0);
                setSelectedReferenceIds([]);
              }}
            >
              从头练习
            </button>
          </div>
          <p className="field-help">
            练习使用内置素材，不调用 AI API，也不会写入你的项目。
          </p>
        </aside>
      </div>
      {highlight && highlight.width > 0 && highlight.height > 0 && (
        <svg className="tutorial-spotlight" aria-hidden="true">
          <defs>
            <mask id={maskId}>
              <rect width="100%" height="100%" fill="white" />
              <rect
                x={highlight.x - 5}
                y={highlight.y - 5}
                width={highlight.width + 10}
                height={highlight.height + 10}
                rx="8"
                fill="black"
              />
            </mask>
          </defs>
          <rect
            width="100%"
            height="100%"
            className="tutorial-dimmer"
            mask={`url(#${maskId})`}
          />
          <rect
            data-tutorial-highlight="true"
            x={highlight.x - 5}
            y={highlight.y - 5}
            width={highlight.width + 10}
            height={highlight.height + 10}
            rx="8"
            fill="none"
            className="tutorial-target-ring"
          />
        </svg>
      )}
    </dialog>
  );
}
