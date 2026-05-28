# 2026-05-20 First Transcript Batch

This folder records the first curated batch of real transcript samples for the summary-quality flywheel.

The original transcript files stay in `legacy-cli/examples/transcripts/`. This batch only stores references and evaluation intent so the CLI keeps working with the flat transcript directory.

## Batch Purpose

- Build the first regression set for meeting and communication summaries.
- Expose routing gaps in the classifier.
- Seed prompt and template improvements for product, marketing, sales, government projects, interviews, and project meetings.
- Mark high-sensitivity samples that need desensitization before public demos.

## Notes

- `03-19 产品：AI助手功能需求评审 2.txt` is a duplicate of `03-19 产品：AI助手功能需求评审.txt` and should not be used as a separate regression case.
- `05-19 政府类：北新泾新朝阳地区城市设计国际征集.txt` is high-value for government project routing and should remain internal-only.
- `技术岗位候选人面试会议纪要.txt` and `01月27日 技术岗面试会议纪要：Web前端工程师.txt` justify adding a dedicated technical interview summary template.
