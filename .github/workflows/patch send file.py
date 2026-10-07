# Adds "file_path" (send a document) to the send_telegram_message tool.
# Run from the unpacked sources root (the folder that contains src/).
# Only files inside $HOME/files and ./marin_world can be sent (checked in C++).
import re, sys

def patch(path, pairs):
    s = open(path, encoding='utf-8').read()
    for old, new in pairs:
        assert s.count(old) == 1, f'{path}: pattern not found exactly once: {old[:70]!r}'
        s = s.replace(old, new, 1)
    open(path, 'w', encoding='utf-8').write(s)
    print('patched', path)

# ---------- util/post_message.h ----------
patch('src/util/post_message.h', [(
"    AOptional<APath> audioPath = std::nullopt,\n    int64_t replyTo = 0);",
"    AOptional<APath> audioPath = std::nullopt,\n    int64_t replyTo = 0,\n    AOptional<APath> documentPath = std::nullopt);")])

# ---------- util/post_message.cpp ----------
patch('src/util/post_message.cpp', [
("AOptional<APath> audioPath, int64_t replyTo) {",
 "AOptional<APath> audioPath, int64_t replyTo, AOptional<APath> documentPath) {"),
("            auto content = td::td_api::make_object<td::td_api::inputMessageText>();",
"""            if (documentPath) {
                auto content = td::td_api::make_object<td::td_api::inputMessageDocument>();
                content->document_ = ITelegramClient::toPtr(td::td_api::inputFileLocal(documentPath->absolute().toStdString()));
                if (!text.empty()) {
                    content->caption_ = [&] {
                        auto t = td::td_api::make_object<td::td_api::formattedText>();
                        t->text_ = text;
                        return t;
                    }();
                }
                return content;
            }

            auto content = td::td_api::make_object<td::td_api::inputMessageText>();"""),
])

# ---------- tools/send_telegram_message.cpp ----------
patch('src/tools/send_telegram_message.cpp', [
("#include <random>\n",
 "#include <random>\n#include <filesystem>\n#include <cstdlib>\n#include <vector>\n"),
# tool parameter
("""                        {"reply_to_message_id", {""",
"""                        {"file_path", {
                            .type = "string",
                            .description = "Sends a file (document) from the laptop. Allowed only inside "
                            "/home/marinka/files and marin_world/ (path relative to the working directory, "
                            "e.g. marin_world/journal.md). Max 20 MB. The text, if any, becomes the caption."},
                        },
                        {"reply_to_message_id", {"""),
# read arg
("""            const auto audioFilename = ctx.args["audio_filename"].asStringOpt().valueOr("");""",
"""            const auto audioFilename = ctx.args["audio_filename"].asStringOpt().valueOr("");
            const auto filePath = ctx.args["file_path"].asStringOpt().valueOr("");"""),
# empty check
("""            if (message.empty() && photoFilename.empty() && audioFilename.empty()) {
                co_return "Error: At least one of \\"text\\", \\"photo_filename\\" or \\"audio_filename\\" must be populated";
            }""",
"""            if (message.empty() && photoFilename.empty() && audioFilename.empty() && filePath.empty()) {
                co_return "Error: At least one of \\"text\\", \\"photo_filename\\", \\"audio_filename\\" or \\"file_path\\" must be populated";
            }
            if (!filePath.empty() && (!photoFilename.empty() || !audioFilename.empty())) {
                co_return "Error: cannot attach a file together with a photo or audio in a single message";
            }"""),
# skip similarity check when a file is attached
("            if (!message.empty() && photoFilename.empty()) {\n                auto target",
 "            if (!message.empty() && photoFilename.empty() && filePath.empty()) {\n                auto target"),
# resolve + validate the path (before the reply_to check)
("""            // Alex2772 (Apr 23 2026):
            //
            // After the introduction of reply_to_message_id""",
"""            AOptional<APath> documentPath;
            if (!filePath.empty()) {
                namespace fs = std::filesystem;
                std::error_code ec;
                const fs::path requested = fs::weakly_canonical(fs::path(filePath.toStdString()), ec);
                if (ec) {
                    throw AException("Invalid file path: {}"_format(filePath));
                }
                std::vector<fs::path> roots;
                if (const char* home = std::getenv("HOME"); home != nullptr) {
                    std::error_code ec2;
                    roots.push_back(fs::weakly_canonical(fs::path(home) / "files", ec2));
                }
                {
                    std::error_code ec2;
                    roots.push_back(fs::weakly_canonical(fs::current_path() / "marin_world", ec2));
                }
                bool allowed = false;
                for (const auto& root : roots) {
                    const auto rel = requested.lexically_relative(root);
                    if (!rel.empty() && rel.begin()->string() != "..") {
                        allowed = true;
                        break;
                    }
                }
                if (!allowed) {
                    throw AException("Sending this file is not allowed. Allowed folders: ~/files and marin_world/");
                }
                if (!fs::is_regular_file(requested, ec)) {
                    throw AException("File not found: {}"_format(filePath));
                }
                const auto size = fs::file_size(requested, ec);
                if (ec || size > 20ull * 1024 * 1024) {
                    throw AException("File is too large (max 20 MB): {}"_format(filePath));
                }
                documentPath = APath(requested.string().c_str());
            }

            // Alex2772 (Apr 23 2026):
            //
            // After the introduction of reply_to_message_id"""),
# the two sendings
("""                                                       std::exchange(audioPath, {}),
                                                       replyTo);""",
"""                                                       std::exchange(audioPath, {}),
                                                       replyTo,
                                                       std::exchange(documentPath, {}));"""),
("""*telegram, chat->id_, message, std::move(photo), std::move(audioPath), replyTo);""",
 """*telegram, chat->id_, message, std::move(photo), std::move(audioPath), replyTo, std::move(documentPath));"""),
])
print('OK')
