# Lightweight Wheel-Candidate Filtering for Virtual Wheel Try-On

Egor Kuznetsov, Nikolai Lutsenko
Skolkovo Institute of Science and Technology
Project proposal for Deep Learning project work
May 2026

## Abstract

This proposal describes a two-week applied deep learning project for a practical part of a virtual wheel try-on pipeline. Given a candidate crop or a candidate region from a vehicle image, the model will classify whether this region is a valid wheel candidate or an invalid false positive. The main goal is to reduce unnecessary calls to expensive vision-language and image-generation models while keeping the pipeline reliable. The project will use transfer learning with compact vision backbones, compare several input formats, and evaluate the model with both classification metrics and deployment-oriented metrics. The final result will include a reproducible dataset pipeline, a trained lightweight model, evaluation results, a short report, and a demonstration.

Index Terms: deep learning, computer vision, transfer learning, wheel detection, virtual try-on, lightweight classification.

## 1. Project Context

The project is connected with a real virtual wheel try-on product. A user provides an image of a vehicle and an image of a wheel or rim. A generative image model then creates a visualization of how the new wheels may look on the car.

Before the system calls expensive downstream components, it needs to decide which proposed wheel regions are useful. Some regions are real wheels. Other regions may be reflections, shadows, background objects, car body parts, or poor crops. Passing these bad candidates further can increase cost, latency, and the risk of poor output images.

This project matches the Deep Learning course requirements because it includes supervised image classification, transfer learning, training and validation protocols, model comparison, error analysis, and deployment-oriented evaluation.

## 2. Problem Statement

The current pipeline can produce several candidate regions around possible wheels. The task is to train a compact binary classifier:

```text
f(x) -> y, where y is in {0, 1}
```

Here, `x` is a candidate crop or candidate-region image. The label `y = 1` means that the region is a valid wheel candidate. The label `y = 0` means that the region is invalid and should not be sent to the expensive downstream stage.

The model is not intended to solve full vehicle recognition, wheel compatibility search, or complete generated-image quality assessment. The scope is intentionally narrow: decide whether one candidate region is useful for the wheel try-on pipeline.

For the future product pipeline, the classifier should be used as a conservative pre-filter. It should reject only clear invalid candidates. Valid and uncertain candidates can still be passed to a stronger vision-language model or to the next pipeline stage. This design reduces cost while limiting the risk of rejecting a true wheel.

## 3. Motivation

Large vision-language models and image-generation APIs are powerful, but they are also slow and relatively expensive. A small local classifier can remove obvious bad candidates before these components are called.

The expected practical benefits are:

- fewer unnecessary vision-language or generation calls;
- lower latency in an interactive user-facing pipeline;
- better robustness against reflections, shadows, and background objects;
- a reusable lightweight model that can run on modest hardware;
- a clear path from a course prototype to a production component.

The topic is also suitable for a deep learning project because it requires dataset preparation, transfer learning, augmentation, threshold tuning, class imbalance handling, and error analysis.

## 4. Proposed Method

### 4.1 Dataset

The dataset will consist of candidate wheel crops or candidate-region images. The preferred source is the existing virtual wheel try-on pipeline. Candidate samples may include:

- correctly detected visible wheels;
- reflections that look similar to wheels;
- wheel arches without visible wheels;
- headlights, bumpers, and car body parts;
- road, background, and random objects;
- partial or badly localized wheels;
- generated or overlay artifacts.

The project will use a binary label scheme:

- `1: valid_wheel_candidate` - a visible and sufficiently localized wheel region that should be processed further;
- `0: invalid_candidate` - a false or unusable candidate that should be filtered out.

Ambiguous samples will be marked as `ignore` during annotation. They will be saved in the annotation files, but they will not be used for the main training set unless a later review assigns a clear label.

A realistic minimum target is 600 to 1,000 manually labeled crops. A stronger version would use 2,000 to 5,000 crops. The train, validation, and test splits must be created by source image, not by individual crop. This prevents near-duplicate crops from the same car image from appearing in both training and testing.

### 4.2 Input Variants

The project will compare several input formats:

- a tight crop around the candidate box;
- a crop with margin and local context;
- an overlay-style crop where the candidate box or mask is visible.

This comparison is useful because a wheel crop often needs context. For example, an isolated round object may look like a wheel, but the nearby tire, wheel arch, and car body can help the model make a better decision.

### 4.3 Models

The project will start with simple baselines:

- majority-class baseline;
- frozen image embeddings with logistic regression, if time permits;
- a small CNN trained from scratch as a sanity check.

The main model will be a compact pretrained vision backbone fine-tuned for binary classification. Candidate architectures include MobileNetV3, EfficientNet-B0, EfficientNetV2-S, and ConvNeXt-Tiny. The final choice will depend on validation performance, inference speed, and model size.

If time permits, we will add a teacher-student or pseudo-labeling experiment. A stronger model or a vision-language model can provide confidence scores for extra candidates, while the compact student model remains the deployable model.

### 4.4 Training

Candidate images will be resized to a fixed resolution, for example `224 x 224`. We will apply moderate augmentations such as horizontal flips, small rotations, brightness and contrast changes, and mild crop variation.

The training process will use a validation split, early stopping, and a standard classification loss. If the dataset is imbalanced, we will use class weighting, balanced sampling, or threshold tuning.

## 5. Evaluation

The model will be evaluated on a held-out test set. Accuracy alone is not enough because the product cost of errors is not symmetric.

The planned metrics are:

- accuracy;
- precision, recall, and F1-score;
- recall for valid wheel candidates;
- false rejection rate for valid wheel candidates;
- ROC-AUC and PR-AUC;
- inference latency per candidate;
- model size.

Recall for valid wheel candidates is the most important product metric. If the classifier rejects a true wheel, the try-on pipeline may fail. Precision is also important because too many false positives still waste downstream computation.

The decision threshold will be selected on the validation set. A practical threshold rule is:

```text
keep valid-wheel recall high first, then maximize the number of invalid candidates rejected
```

For a production-oriented mode, the classifier can use three decisions:

```text
confident invalid -> reject
valid or uncertain -> pass to VLM or downstream pipeline
```

This conservative design helps reduce cost without making the lightweight model the only decision-maker.

## 6. Work Plan and Responsibilities

The project is planned for approximately two weeks.

| Period | Work |
|---|---|
| Days 1-2 | Define labels, collect candidate crops, create dataset structure. |
| Days 3-4 | Manual labeling, cleaning, split creation by source image, class balance analysis. |
| Days 5-6 | Implement baselines and data loaders. |
| Days 7-9 | Fine-tune lightweight pretrained models and compare input variants. |
| Days 10-11 | Tune threshold, analyze errors, and run optional teacher or pseudo-labeling experiment. |
| Days 12-14 | Prepare report, figures, model card, and short demo or presentation. |

Egor Kuznetsov will focus on dataset preprocessing, model training, experiment tracking, and metric evaluation. Nikolai Lutsenko will focus on product context, candidate generation logic, data collection from the wheel try-on pipeline, quality requirements, and demo integration. Additional team members can contribute to annotation, baselines, report writing, and presentation preparation.

## 7. Risks

The main risks are limited labeled data, ambiguous labels, data leakage, and overfitting. To reduce these risks, the project will use simple label definitions, a clean dataset structure, train/validation/test split by source image, transfer learning, and separate validation and test metrics.

Another important risk is changing candidate boxes during annotation. If annotators turn bad automatic boxes into ideal manual boxes, the model may learn from a distribution that is different from the real production pipeline. Therefore, automatic candidate boxes should normally be labeled as they are. Manual boxes should be created only when the annotation task explicitly asks for new examples.

If full integration into the product pipeline becomes too time-consuming, the core deliverable will remain the trained model and a reproducible evaluation script or notebook.

## 8. Expected Deliverables

The expected deliverables are:

- labeled dataset or reproducible dataset-building script;
- annotation guide and dataset schema;
- training notebook or Python script;
- trained lightweight model checkpoint;
- evaluation tables and confusion matrix;
- threshold analysis for conservative filtering;
- latency and model-size measurements;
- concise report and presentation;
- optional demo showing candidate filtering before downstream processing.

## 9. Conclusion

This project proposes a focused and realistic deep learning component for a virtual wheel try-on product. Instead of attempting broad vehicle recognition or full visual quality assessment, it targets a narrow decision with direct product value: filtering valid and invalid wheel candidates. The task has clear inputs, labels, metrics, and practical constraints. It is suitable for a two-week course project and can also become a useful production component after further validation.

## References

[1] Skolkovo Institute of Science and Technology, "DA030057 Deep Learning: Course Syllabus," local course document, 2026.

[2] AIML API Documentation, "Reve image model endpoints." Available: https://docs.aimlapi.com/api-references/image-models/reve

[3] L. Yang, P. Luo, C. C. Loy, and X. Tang, "A Large-Scale Car Dataset for Fine-Grained Categorization and Verification," arXiv:1506.08959, 2015.
