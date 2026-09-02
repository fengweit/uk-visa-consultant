import Vision
import AppKit
import Foundation

let args = CommandLine.arguments
guard args.count == 2 else { fputs("usage: vision_ocr IMAGE\n", stderr); exit(2) }
guard let image = NSImage(contentsOfFile: args[1]),
      let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    fputs("failed to load image\n", stderr); exit(3)
}
let request = VNRecognizeTextRequest()
request.recognitionLanguages = ["en-US", "zh-Hans"]
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
do { try handler.perform([request]) } catch {
    fputs("OCR failed: \(error)\n", stderr); exit(4)
}
let rows = (request.results ?? []).compactMap { observation -> (CGFloat, CGFloat, String, Float)? in
    guard let candidate = observation.topCandidates(1).first else { return nil }
    return (observation.boundingBox.maxY, observation.boundingBox.minX, candidate.string, candidate.confidence)
}.sorted { a, b in abs(a.0 - b.0) > 0.015 ? a.0 > b.0 : a.1 < b.1 }
for row in rows { print("\(row.3)\t\(row.2)") }
