import { describe, expect, it } from "vitest";
import {
  advanceTutorial,
  TUTORIAL_MODULES,
  TUTORIAL_STEPS,
  TUTORIAL_STORY,
  TUTORIAL_REFERENCE_ASSETS,
  tutorialReferencesValid,
} from "./tutorialData";

describe("offline tutorial", () => {
  it("requires exactly the assets needed by the first shot", () => {
    expect(tutorialReferencesValid([])).toBe(false);
    expect(tutorialReferencesValid(["lin-wan"])).toBe(false);
    expect(tutorialReferencesValid(["station"])).toBe(false);
    expect(tutorialReferencesValid(["lin-wan", "chen-shu"])).toBe(false);
    expect(
      tutorialReferencesValid(TUTORIAL_REFERENCE_ASSETS.map((asset) => asset.id)),
    ).toBe(false);
    expect(tutorialReferencesValid(["lin-wan", "lin-wan"])).toBe(false);
    expect(tutorialReferencesValid(["station", "lin-wan"])).toBe(true);
    const targets = TUTORIAL_STEPS.map((step) => step.target);
    expect(targets.indexOf("reference-selection")).toBe(
      targets.indexOf("generate-shots") + 1,
    );
    expect(targets.indexOf("generate-images")).toBe(
      targets.indexOf("reference-selection") + 1,
    );
  });

  it("requires the current target and stops at completion", () => {
    expect(advanceTutorial(0, "generate-videos")).toBe(0);
    let index = 0;
    for (const step of TUTORIAL_STEPS.slice(0, -1))
      index = advanceTutorial(index, step.target);
    expect(index).toBe(TUTORIAL_STEPS.length - 1);
    expect(advanceTutorial(index, TUTORIAL_STEPS[index].target)).toBe(index);
  });

  it("covers every production module with coherent reusable fixtures", () => {
    expect(new Set(TUTORIAL_STEPS.map((step) => step.module))).toEqual(
      new Set(TUTORIAL_MODULES.map((module) => module.id)),
    );
    expect(new Set(TUTORIAL_STEPS.map((step) => step.target)).size).toBe(
      TUTORIAL_STEPS.length,
    );
    for (const character of TUTORIAL_STORY.bible.characters)
      expect(TUTORIAL_STORY.novel).toContain(character.name);
    expect(TUTORIAL_STORY.novel).toContain(TUTORIAL_STORY.bible.location.name);
    expect(TUTORIAL_STORY.shots).toHaveLength(4);
    expect(TUTORIAL_STORY.shots.map((shot) => shot.number)).toEqual([1, 2, 3, 4]);
    for (const shot of TUTORIAL_STORY.shots) {
      expect(shot.prompt).not.toBe("");
      if (shot.dialogue)
        expect(TUTORIAL_STORY.scene.dialogue.join("\n")).toContain(shot.dialogue);
    }
  });
});
