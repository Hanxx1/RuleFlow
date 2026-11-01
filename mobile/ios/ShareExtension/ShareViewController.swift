import UIKit
import UniformTypeIdentifiers

final class ShareViewController: UIViewController {
    private let suite = "group.com.zhishi.ruleflow"
    private let maxBytes = 20 * 1024 * 1024
    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        Task { await receive() }
    }
    private func receive() async {
        var items: [[String: Any]] = []
        let providers = (extensionContext?.inputItems as? [NSExtensionItem] ?? []).flatMap { $0.attachments ?? [] }.prefix(10)
        for provider in providers {
            if provider.hasItemConformingToTypeIdentifier(UTType.url.identifier), let url = try? await provider.loadItem(forTypeIdentifier: UTType.url.identifier) as? URL {
                items.append(["id": UUID().uuidString, "kind": "url", "text": url.absoluteString, "state": "pending"])
            } else if provider.hasItemConformingToTypeIdentifier(UTType.plainText.identifier), let text = try? await provider.loadItem(forTypeIdentifier: UTType.plainText.identifier) as? String {
                items.append(["id": UUID().uuidString, "kind": "text", "text": text, "state": "pending"])
            } else if provider.hasItemConformingToTypeIdentifier(UTType.data.identifier), let url = try? await provider.loadFileRepresentation(forTypeIdentifier: UTType.data.identifier) {
                items.append(copyToGroup(url))
            }
        }
        let defaults = UserDefaults(suiteName: suite)
        var queue = defaults?.array(forKey: "pending_imports") as? [[String: Any]] ?? []
        queue.append(contentsOf: items); defaults?.set(queue, forKey: "pending_imports")
        extensionContext?.completeRequest(returningItems: nil)
    }
    private func copyToGroup(_ source: URL) -> [String: Any] {
        let id = UUID().uuidString
        guard let size = (try? source.resourceValues(forKeys: [.fileSizeKey]).fileSize), size <= maxBytes,
              let root = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: suite) else {
            return ["id": id, "state": "failed", "error": "file_too_large_or_group_unavailable"]
        }
        let target = root.appendingPathComponent("shared_\(id)_\(source.lastPathComponent)")
        do { try FileManager.default.copyItem(at: source, to: target); return ["id": id, "kind": "file", "local_ref": target.lastPathComponent, "size": size, "state": "pending"] }
        catch { return ["id": id, "state": "failed", "error": "copy_failed"] }
    }
}
