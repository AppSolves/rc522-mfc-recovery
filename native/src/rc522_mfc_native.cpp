#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <csignal>
#include <cctype>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

#include "MFrec.h"
#include "RC522.h"
#include "crapto1.h"

namespace {

using Key = std::array<byte, 6>;
std::atomic<bool> g_stop{false};

constexpr auto PROGRESS_HEARTBEAT = std::chrono::milliseconds(750);
constexpr std::size_t HARDNESTED_ATTEMPT_MULTIPLIER = 10;
constexpr std::size_t HARDNESTED_MIN_EXTRA_ATTEMPTS = 1000;
constexpr std::size_t HARDNESTED_MAX_CONSECUTIVE_FAILURES = 250;

void on_signal(int) { g_stop.store(true); }

void sleep_ms(unsigned ms) {
    std::this_thread::sleep_for(std::chrono::milliseconds(ms));
}

std::string json_escape(const std::string &value) {
    std::ostringstream out;
    for (unsigned char c : value) {
        switch (c) {
            case '"': out << "\\\""; break;
            case '\\': out << "\\\\"; break;
            case '\n': out << "\\n"; break;
            case '\r': out << "\\r"; break;
            case '\t': out << "\\t"; break;
            default:
                if (c < 0x20) {
                    out << "\\u" << std::hex << std::setw(4) << std::setfill('0')
                        << static_cast<int>(c) << std::dec;
                } else {
                    out << c;
                }
        }
    }
    return out.str();
}

void emit_json(const std::string &payload) {
    std::cout << "RC522_JSON:" << payload << std::endl;
}

struct ProgressDetails {
    int sector = -1;
    char key_type = '\0';
    std::size_t attempts = 0;
    std::size_t max_attempts = 0;
    std::size_t consecutive_failures = 0;
    bool include_attempts = false;
};

void emit_progress(
    const std::string &operation,
    std::size_t completed,
    std::size_t total,
    const ProgressDetails &details = {}
) {
    std::ostringstream json;
    json << "{\"operation\":\"" << json_escape(operation)
         << "\",\"completed\":" << completed
         << ",\"total\":" << total;
    if (details.sector >= 0) {
        json << ",\"sector\":" << details.sector;
    }
    if (details.key_type != '\0') {
        json << ",\"key_type\":\"" << details.key_type << '"';
    }
    if (details.include_attempts) {
        json << ",\"attempts\":" << details.attempts
             << ",\"max_attempts\":" << details.max_attempts
             << ",\"consecutive_failures\":" << details.consecutive_failures;
    }
    json << '}';
    std::cerr << "RC522_PROGRESS:" << json.str() << std::endl;
}

struct Args {
    std::string command;
    std::unordered_map<std::string, std::string> values;
    std::unordered_set<std::string> flags;

    bool has(const std::string &name) const {
        return values.count(name) || flags.count(name);
    }

    std::string get(const std::string &name, const std::string &fallback = "") const {
        auto it = values.find(name);
        return it == values.end() ? fallback : it->second;
    }

    int get_int(const std::string &name, int fallback) const {
        auto it = values.find(name);
        if (it == values.end()) return fallback;
        return std::stoi(it->second);
    }
};

Args parse_args(int argc, char **argv) {
    if (argc < 2) throw std::runtime_error("missing command");
    Args result;
    result.command = argv[1];
    for (int i = 2; i < argc; ++i) {
        std::string token = argv[i];
        if (token.rfind("--", 0) != 0) {
            throw std::runtime_error("unexpected positional argument: " + token);
        }
        if (i + 1 < argc && std::string(argv[i + 1]).rfind("--", 0) != 0) {
            result.values[token] = argv[++i];
        } else {
            result.flags.insert(token);
        }
    }
    return result;
}

std::string required(const Args &args, const std::string &name) {
    const std::string value = args.get(name);
    if (value.empty()) throw std::runtime_error("missing required option " + name);
    return value;
}

byte auth_type(const std::string &value) {
    if (value == "A" || value == "a") return AUTHENT_A;
    if (value == "B" || value == "b") return AUTHENT_B;
    throw std::runtime_error("key type must be A or B");
}

char auth_name(byte command) { return command == AUTHENT_B ? 'B' : 'A'; }

bool parse_key(const std::string &text, Key &key) {
    if (text.size() != 12) return false;
    for (char c : text) {
        if (!std::isxdigit(static_cast<unsigned char>(c))) return false;
    }
    try {
        for (std::size_t i = 0; i < key.size(); ++i) {
            key[i] = static_cast<byte>(std::stoul(text.substr(i * 2, 2), nullptr, 16));
        }
    } catch (...) {
        return false;
    }
    return true;
}

std::string format_key(const Key &key) {
    std::ostringstream out;
    out << std::uppercase << std::hex << std::setfill('0');
    for (byte b : key) out << std::setw(2) << static_cast<unsigned>(b);
    return out.str();
}

std::string format_uid(uint32_t uid) {
    std::ostringstream out;
    out << std::uppercase << std::hex << std::setw(8) << std::setfill('0') << uid;
    return out.str();
}

std::vector<int> parse_sectors(const std::string &expression) {
    std::set<int> values;
    std::stringstream ss(expression);
    std::string part;
    while (std::getline(ss, part, ',')) {
        if (part.empty()) continue;
        const auto dash = part.find('-');
        if (dash == std::string::npos) {
            values.insert(std::stoi(part));
        } else {
            const int first = std::stoi(part.substr(0, dash));
            const int last = std::stoi(part.substr(dash + 1));
            if (first > last) throw std::runtime_error("invalid sector range");
            for (int value = first; value <= last; ++value) values.insert(value);
        }
    }
    for (int value : values) {
        if (value < 0 || value > 15) throw std::runtime_error("only MIFARE Classic 1K sectors 0-15 are supported");
    }
    return {values.begin(), values.end()};
}

std::vector<Key> load_keys(const std::string &filename) {
    std::ifstream input(filename);
    if (!input) throw std::runtime_error("cannot open key file: " + filename);
    std::vector<Key> keys;
    std::set<std::string> unique;
    std::string line;
    while (std::getline(input, line)) {
        const auto comment = line.find('#');
        if (comment != std::string::npos) line.erase(comment);
        line.erase(std::remove_if(line.begin(), line.end(), [](unsigned char c) { return std::isspace(c); }), line.end());
        Key key{};
        if (!line.empty() && parse_key(line, key)) {
            const auto formatted = format_key(key);
            if (unique.insert(formatted).second) keys.push_back(key);
        }
    }
    return keys;
}

void reset_card(RC522 &reader, unsigned wait_ms = 5) {
    reader.stopCrypto();
    reader.antennaOff();
    sleep_ms(wait_ms);
    reader.antennaOn();
    sleep_ms(wait_ms);
}

bool authenticate_fresh(RC522 &reader, byte type, byte block, Key &key) {
    reset_card(reader);
    if (!reader.selectCard(20, 5)) return false;
    return reader.authenticateOnChip(type, block, key.data());
}

bool canonical_weak_nonce(uint32_t nonce) {
    const uint16_t upper = static_cast<uint16_t>(nonce >> 16);
    const uint16_t lower = static_cast<uint16_t>(nonce & 0xFFFFU);
    return static_cast<uint16_t>(prng_successor(upper, 16)) == lower;
}

byte odd_parity(byte value) {
    return static_cast<byte>((0x9669U >> ((value ^ (value >> 4)) & 0x0FU)) & 1U);
}

uint32_t decrypt_nested_nonce(uint32_t uid, uint32_t encrypted_nonce, uint64_t key) {
    Crypto1State *state = crypto1_create(key);
    if (state == nullptr) throw std::runtime_error("crypto1_create failed");
    const uint32_t plain = encrypted_nonce ^ crypto1_word(state, encrypted_nonce ^ uid, 1);
    crypto1_destroy(state);
    return plain;
}

uint64_t key_to_integer(const Key &key) {
    uint64_t result = 0;
    for (byte value : key) result = (result << 8) | value;
    return result;
}

bool validate_parity(uint32_t plain_nonce, uint32_t encrypted_nonce, byte packed) {
    const uint32_t stream = plain_nonce ^ encrypted_nonce;
    const byte p0 = static_cast<byte>((plain_nonce >> 24) & 0xFF);
    const byte p1 = static_cast<byte>((plain_nonce >> 16) & 0xFF);
    const byte p2 = static_cast<byte>((plain_nonce >> 8) & 0xFF);
    return odd_parity(p0) == (((packed >> 0) & 1U) ^ ((stream >> 16) & 1U)) &&
           odd_parity(p1) == (((packed >> 1) & 1U) ^ ((stream >> 8) & 1U)) &&
           odd_parity(p2) == (((packed >> 2) & 1U) ^ ((stream >> 0) & 1U));
}

int command_reader_version(const Args &) {
    RC522 reader;
    reader.setQuiet(true);
    const byte version = reader.getVersion();
    std::ostringstream json;
    json << "{\"ok\":true,\"version\":" << static_cast<unsigned>(version)
         << ",\"version_hex\":\"" << std::uppercase << std::hex << std::setw(2)
         << std::setfill('0') << static_cast<unsigned>(version) << "\"}";
    emit_json(json.str());
    return (version == 0x00 || version == 0xFF) ? 2 : 0;
}

int command_identify(const Args &) {
    RC522 reader;
    reader.setQuiet(true);
    if (!reader.selectCard(50, 10)) throw std::runtime_error("no supported MIFARE Classic 1K card detected");
    std::ostringstream json;
    json << "{\"ok\":true,\"uid\":\"" << format_uid(reader.getUID())
         << "\",\"atqa\":\"0400\",\"sak\":\"08\",\"type\":\"MIFARE Classic 1K\","
         << "\"reader_version\":\"" << std::uppercase << std::hex << std::setw(2)
         << std::setfill('0') << static_cast<unsigned>(reader.getVersion()) << "\"}";
    emit_json(json.str());
    return 0;
}

int command_auth(const Args &args) {
    const int block = std::stoi(required(args, "--block"));
    if (block < 0 || block > 63) throw std::runtime_error("block must be 0-63");
    const byte type = auth_type(required(args, "--key-type"));
    Key key{};
    if (!parse_key(required(args, "--key"), key)) throw std::runtime_error("key must be 12 hexadecimal characters");
    RC522 reader;
    reader.setQuiet(true);
    const bool success = authenticate_fresh(reader, type, static_cast<byte>(block), key);
    std::ostringstream json;
    json << "{\"ok\":" << (success ? "true" : "false") << ",\"authenticated\":"
         << (success ? "true" : "false") << ",\"block\":" << block
         << ",\"key_type\":\"" << auth_name(type) << "\",\"key\":\"" << format_key(key) << "\"}";
    emit_json(json.str());
    return success ? 0 : 3;
}

int command_keyscan(const Args &args) {
    const auto keys = load_keys(required(args, "--keys"));
    const auto sectors = parse_sectors(args.get("--sectors", "0-15"));
    if (keys.empty()) {
        throw std::runtime_error("key file contains no valid keys");
    }

    RC522 reader;
    reader.setQuiet(true);
    if (!reader.selectCard(50, 10)) {
        throw std::runtime_error("card not detected");
    }
    const std::string uid = format_uid(reader.getUID());

    struct Hit {
        int sector;
        char type;
        std::string key;
        std::string method;
    };
    std::vector<Hit> hits;
    const std::size_t total_keys = keys.size();

    auto emit_keyscan_progress = [total_keys](std::size_t tested, int sector, char type) {
        ProgressDetails details;
        details.sector = sector;
        details.key_type = type;
        emit_progress("keyscan", tested, total_keys, details);
    };

    for (int sector : sectors) {
        const byte trailer_block = static_cast<byte>(sector * 4 + 3);
        bool found_a = false;
        bool found_b = false;
        std::size_t tested_a = 0;
        std::size_t tested_b = 0;
        std::size_t reported_a = 0;
        std::size_t reported_b = 0;
        auto last_a_progress = std::chrono::steady_clock::now();

        emit_keyscan_progress(0, sector, 'A');
        for (Key candidate : keys) {
            if (g_stop.load()) break;
            ++tested_a;
            const bool authenticated = authenticate_fresh(
                reader,
                AUTHENT_A,
                trailer_block,
                candidate
            );
            const auto now = std::chrono::steady_clock::now();
            if (now - last_a_progress >= PROGRESS_HEARTBEAT) {
                emit_keyscan_progress(tested_a, sector, 'A');
                reported_a = tested_a;
                last_a_progress = now;
            }
            if (!authenticated) {
                continue;
            }

            found_a = true;
            hits.push_back({sector, 'A', format_key(candidate), "dictionary"});

            // Depending on the access bits, Key B can be readable as data after
            // authenticating with Key A. Never trust the bytes blindly. Verify
            // the extracted value by a fresh Key B authentication first.
            byte trailer[18] = {0};
            if (reader.readBlock(trailer_block, trailer, sizeof(trailer))) {
                Key exposed_b{};
                std::copy(trailer + 10, trailer + 16, exposed_b.begin());
                if (authenticate_fresh(reader, AUTHENT_B, trailer_block, exposed_b)) {
                    found_b = true;
                    hits.push_back(
                        {sector, 'B', format_key(exposed_b), "sector-trailer"}
                    );
                }
            }
            break;
        }
        if (tested_a != reported_a) {
            emit_keyscan_progress(tested_a, sector, 'A');
        }

        if (!found_b) {
            emit_keyscan_progress(0, sector, 'B');
            auto last_b_progress = std::chrono::steady_clock::now();
            for (Key candidate : keys) {
                if (g_stop.load()) break;
                ++tested_b;
                const bool authenticated = authenticate_fresh(
                    reader,
                    AUTHENT_B,
                    trailer_block,
                    candidate
                );
                const auto now = std::chrono::steady_clock::now();
                if (now - last_b_progress >= PROGRESS_HEARTBEAT) {
                    emit_keyscan_progress(tested_b, sector, 'B');
                    reported_b = tested_b;
                    last_b_progress = now;
                }
                if (authenticated) {
                    found_b = true;
                    hits.push_back(
                        {sector, 'B', format_key(candidate), "dictionary"}
                    );
                    break;
                }
            }
            if (tested_b != reported_b) {
                emit_keyscan_progress(tested_b, sector, 'B');
            }
        }

        (void)found_a;
    }

    std::ostringstream json;
    json << "{\"ok\":true,\"uid\":\"" << uid
         << "\",\"tested_keys\":" << keys.size() << ",\"hits\":[";
    for (std::size_t index = 0; index < hits.size(); ++index) {
        if (index) json << ',';
        json << "{\"sector\":" << hits[index].sector
             << ",\"key_type\":\"" << hits[index].type
             << "\",\"key\":\"" << hits[index].key
             << "\",\"method\":\"" << hits[index].method << "\"}";
    }
    json << "]}";
    emit_json(json.str());
    return 0;
}

int command_nonce_probe(const Args &args) {
    const int block = args.get_int("--block", 0);
    const int wanted = args.get_int("--samples", 128);
    if (block < 0 || block > 63 || wanted < 1) throw std::runtime_error("invalid block or sample count");
    MFrec reader;
    reader.setQuiet(true);
    std::unordered_map<uint32_t, int> frequency;
    int weak = 0;
    int collected = 0;
    const int maximum_attempts = std::max(wanted * 4, wanted + 32);
    auto last_progress = std::chrono::steady_clock::now();
    auto emit_nonce_progress = [&](int attempts) {
        ProgressDetails details;
        details.include_attempts = true;
        details.attempts = static_cast<std::size_t>(attempts);
        details.max_attempts = static_cast<std::size_t>(maximum_attempts);
        emit_progress(
            "nonce-probe",
            static_cast<std::size_t>(collected),
            static_cast<std::size_t>(wanted),
            details
        );
    };

    emit_nonce_progress(0);
    int attempts = 0;
    for (; attempts < maximum_attempts && collected < wanted && !g_stop.load(); ++attempts) {
        uint32_t nonce = 0;
        if (reader.sampleNonce(AUTHENT_A, static_cast<byte>(block), &nonce)) {
            ++collected;
            ++frequency[nonce];
            if (canonical_weak_nonce(nonce)) ++weak;
        }
        const auto now = std::chrono::steady_clock::now();
        if (now - last_progress >= PROGRESS_HEARTBEAT || collected == wanted) {
            emit_nonce_progress(attempts + 1);
            last_progress = now;
        }
    }
    if (collected < wanted) {
        emit_nonce_progress(attempts);
    }
    if (collected == 0) throw std::runtime_error("could not collect nonces");
    int max_repeat = 0;
    for (const auto &item : frequency) max_repeat = std::max(max_repeat, item.second);
    std::string classification;
    if (frequency.size() == 1 || max_repeat >= static_cast<int>(collected * 0.95)) classification = "static";
    else if (weak >= static_cast<int>(collected * 0.90)) classification = "weak";
    else classification = "hard";
    std::ostringstream json;
    json << "{\"ok\":true,\"classification\":\"" << classification << "\",\"samples\":"
         << collected << ",\"unique\":" << frequency.size() << ",\"weak_matches\":" << weak
         << ",\"max_repetition\":" << max_repeat << "}";
    emit_json(json.str());
    return 0;
}

int command_weak_nested(const Args &args) {
    const int known_block = std::stoi(required(args, "--known-block"));
    const int target_block = std::stoi(required(args, "--target-block"));
    const byte known_type = auth_type(required(args, "--known-key-type"));
    const byte target_type = auth_type(required(args, "--target-key-type"));
    if (known_block < 0 || known_block > 63 || target_block < 0 || target_block > 63) throw std::runtime_error("blocks must be 0-63");
    Key known_key{};
    if (!parse_key(required(args, "--known-key"), known_key)) throw std::runtime_error("known key is invalid");
    Key recovered{};
    MFrec reader;
    reader.setQuiet(false);
    const bool success = reader.recoverWeakNested(
        known_type,
        static_cast<byte>(known_block),
        known_key.data(),
        target_type,
        static_cast<byte>(target_block),
        recovered.data()
    );
    std::ostringstream json;
    json << "{\"ok\":" << (success ? "true" : "false") << ",\"recovered\":" << (success ? "true" : "false")
         << ",\"target_block\":" << target_block << ",\"target_key_type\":\"" << auth_name(target_type) << "\"";
    if (success) json << ",\"key\":\"" << format_key(recovered) << "\"";
    json << '}';
    emit_json(json.str());
    return success ? 0 : 4;
}

int command_collect_hardnested(const Args &args) {
    const int known_block = std::stoi(required(args, "--known-block"));
    const int target_block = std::stoi(required(args, "--target-block"));
    const int wanted = std::stoi(required(args, "--samples"));
    const byte known_type = auth_type(required(args, "--known-key-type"));
    const byte target_type = auth_type(required(args, "--target-key-type"));
    const std::string output_name = required(args, "--output");
    if (known_block < 0 || known_block > 63 || target_block < 0 || target_block > 63 || wanted < 2 || wanted % 2 != 0) {
        throw std::runtime_error("blocks must be 0-63 and sample count must be a positive even number");
    }
    Key known_key{};
    if (!parse_key(required(args, "--known-key"), known_key)) throw std::runtime_error("known key is invalid");
    Key validation_key{};
    const bool validation = args.has("--validation-key");
    if (validation && !parse_key(required(args, "--validation-key"), validation_key)) throw std::runtime_error("validation key is invalid");

    const std::string meta_name = args.get("--meta", output_name + ".meta");
    std::ofstream output(output_name, std::ios::binary | std::ios::trunc);
    if (!output) throw std::runtime_error("cannot create output file");

    MFrec reader;
    reader.setQuiet(true);
    if (!reader.selectCard(50, 10)) throw std::runtime_error("card not detected");
    const uint32_t uid = reader.getUID();
    const auto started = std::chrono::steady_clock::now();
    std::unordered_set<uint32_t> unique;
    std::array<bool, 256> first_byte_seen{};
    std::size_t collected = 0;
    std::size_t attempts = 0;
    std::size_t parity_valid = 0;
    std::size_t consecutive_failures = 0;
    const std::size_t wanted_count = static_cast<std::size_t>(wanted);
    const std::size_t max_attempts = std::max(
        wanted_count * HARDNESTED_ATTEMPT_MULTIPLIER,
        wanted_count + HARDNESTED_MIN_EXTRA_ATTEMPTS
    );
    auto last_progress = std::chrono::steady_clock::now();
    auto emit_hardnested_progress = [&]() {
        ProgressDetails details;
        details.include_attempts = true;
        details.attempts = attempts;
        details.max_attempts = max_attempts;
        details.consecutive_failures = consecutive_failures;
        emit_progress("hardnested", collected, wanted_count, details);
    };

    emit_hardnested_progress();

    while (
        collected < wanted_count &&
        attempts < max_attempts &&
        consecutive_failures < HARDNESTED_MAX_CONSECUTIVE_FAILURES &&
        !g_stop.load()
    ) {
        ++attempts;
        uint32_t encrypted_nonce = 0;
        byte encrypted_parity = 0;
        if (!reader.collectHardnestedNonce(
                known_type,
                static_cast<byte>(known_block),
                known_key.data(),
                target_type,
                static_cast<byte>(target_block),
                &encrypted_nonce,
                &encrypted_parity)) {
            ++consecutive_failures;
            const auto now = std::chrono::steady_clock::now();
            if (now - last_progress >= PROGRESS_HEARTBEAT) {
                emit_hardnested_progress();
                output.flush();
                last_progress = now;
            }
            continue;
        }
        consecutive_failures = 0;
        const std::array<byte, 5> record{
            static_cast<byte>((encrypted_nonce >> 24) & 0xFF),
            static_cast<byte>((encrypted_nonce >> 16) & 0xFF),
            static_cast<byte>((encrypted_nonce >> 8) & 0xFF),
            static_cast<byte>(encrypted_nonce & 0xFF),
            static_cast<byte>(encrypted_parity & 0x0F)
        };
        output.write(reinterpret_cast<const char *>(record.data()), static_cast<std::streamsize>(record.size()));
        if (!output) throw std::runtime_error("failed writing nonce dataset");
        ++collected;
        unique.insert(encrypted_nonce);
        first_byte_seen[record[0]] = true;
        if (validation) {
            const auto plain = decrypt_nested_nonce(uid, encrypted_nonce, key_to_integer(validation_key));
            if (validate_parity(plain, encrypted_nonce, encrypted_parity)) ++parity_valid;
        }
        const auto now = std::chrono::steady_clock::now();
        if (now - last_progress >= PROGRESS_HEARTBEAT || collected == wanted_count) {
            emit_hardnested_progress();
            output.flush();
            last_progress = now;
        }
    }
    output.flush();
    if (collected < wanted_count) {
        emit_hardnested_progress();
    }
    const auto elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
    std::size_t coverage = 0;
    for (bool value : first_byte_seen) if (value) ++coverage;

    std::ofstream meta(meta_name, std::ios::trunc);
    meta << "format=RC522-HARDNESTED-RECORDS-V1\n"
         << "record_size=5\n"
         << "nonce_byte_order=big-endian\n"
         << "parity_bit_0=nonce_byte_0\n"
         << "uid=" << format_uid(uid) << '\n'
         << "known_block=" << known_block << '\n'
         << "known_key_type=" << auth_name(known_type) << '\n'
         << "target_block=" << target_block << '\n'
         << "target_key_type=" << auth_name(target_type) << '\n'
         << "records=" << collected << '\n'
         << "attempts=" << attempts << '\n'
         << "unique_nonces=" << unique.size() << '\n'
         << "first_byte_coverage=" << coverage << '\n'
         << "elapsed_seconds=" << elapsed << '\n';
    if (validation) meta << "validation_successes=" << parity_valid << '\n';

    const bool complete = collected == wanted_count;
    std::string error;
    if (!complete) {
        if (g_stop.load()) {
            error = "interrupted while collecting Hardnested traces";
        } else if (consecutive_failures >= HARDNESTED_MAX_CONSECUTIVE_FAILURES) {
            error = "Hardnested trace collection stalled after repeated authentication failures";
        } else if (attempts >= max_attempts) {
            error = "Hardnested trace collection reached the attempt limit before collecting enough samples";
        } else {
            error = "Hardnested trace collection stopped before collecting enough samples";
        }
    }
    std::ostringstream json;
    json << "{\"ok\":" << (complete ? "true" : "false") << ",\"uid\":\"" << format_uid(uid)
         << "\",\"records\":" << collected << ",\"attempts\":" << attempts << ",\"unique\":" << unique.size()
         << ",\"first_byte_coverage\":" << coverage << ",\"output\":\"" << json_escape(output_name)
         << "\",\"meta\":\"" << json_escape(meta_name) << "\"";
    if (validation) json << ",\"validation_successes\":" << parity_valid;
    if (!complete) json << ",\"error\":\"" << json_escape(error) << "\"";
    json << '}';
    emit_json(json.str());
    return complete ? 0 : (g_stop.load() ? 130 : 5);
}

struct SectorKeys { bool has_a = false; bool has_b = false; Key a{}; Key b{}; };

std::map<int, SectorKeys> load_key_map(const std::string &filename) {
    std::ifstream input(filename);
    if (!input) throw std::runtime_error("cannot open key map: " + filename);
    std::map<int, SectorKeys> result;
    std::string line;
    while (std::getline(input, line)) {
        if (line.empty() || line[0] == '#') continue;
        std::replace(line.begin(), line.end(), ',', ' ');
        std::stringstream ss(line);
        int sector;
        char type;
        std::string text;
        if (!(ss >> sector >> type >> text)) continue;
        if (sector < 0 || sector > 15) continue;
        Key key{};
        if (!parse_key(text, key)) continue;
        if (type == 'A' || type == 'a') { result[sector].a = key; result[sector].has_a = true; }
        if (type == 'B' || type == 'b') { result[sector].b = key; result[sector].has_b = true; }
    }
    return result;
}

int command_dump(const Args &args) {
    const auto key_map = load_key_map(required(args, "--key-map"));
    const std::string output_name = required(args, "--output");
    std::array<byte, 1024> dump{};
    RC522 reader;
    reader.setQuiet(true);
    if (!reader.selectCard(50, 10)) {
        throw std::runtime_error("card not detected");
    }

    for (int sector = 0; sector < 16; ++sector) {
        const auto iterator = key_map.find(sector);
        if (
            iterator == key_map.end() ||
            (!iterator->second.has_a && !iterator->second.has_b)
        ) {
            throw std::runtime_error(
                "missing both keys for sector " + std::to_string(sector)
            );
        }

        const SectorKeys &sector_keys = iterator->second;
        for (int offset = 0; offset < 4; ++offset) {
            const int block = sector * 4 + offset;
            bool block_read = false;
            byte buffer[18] = {0};

            for (int choice = 0; choice < 2 && !block_read; ++choice) {
                const bool use_a = choice == 0;
                if ((use_a && !sector_keys.has_a) || (!use_a && !sector_keys.has_b)) {
                    continue;
                }

                Key candidate = use_a ? sector_keys.a : sector_keys.b;
                const byte type = use_a ? AUTHENT_A : AUTHENT_B;
                if (!authenticate_fresh(
                        reader,
                        type,
                        static_cast<byte>(block),
                        candidate
                    )) {
                    continue;
                }

                block_read = reader.readBlock(
                    static_cast<byte>(block),
                    buffer,
                    sizeof(buffer)
                );
            }

            if (!block_read) {
                throw std::runtime_error(
                    "could not read block " + std::to_string(block)
                );
            }

            std::copy(buffer, buffer + 16, dump.begin() + block * 16);
        }

        // MIFARE Classic never reveals Key A when a sector trailer is read.
        // Replace masked key fields with verified recovered keys so the exported
        // image is useful to standard dump-analysis tools.
        const int trailer_offset = (sector * 4 + 3) * 16;
        if (sector_keys.has_a) {
            std::copy(
                sector_keys.a.begin(),
                sector_keys.a.end(),
                dump.begin() + trailer_offset
            );
        }
        if (sector_keys.has_b) {
            std::copy(
                sector_keys.b.begin(),
                sector_keys.b.end(),
                dump.begin() + trailer_offset + 10
            );
        }
    }

    std::ofstream output(output_name, std::ios::binary | std::ios::trunc);
    output.write(
        reinterpret_cast<const char *>(dump.data()),
        static_cast<std::streamsize>(dump.size())
    );
    if (!output) {
        throw std::runtime_error("failed writing dump");
    }

    std::ostringstream json;
    json << "{\"ok\":true,\"bytes\":1024,\"keys_injected\":true,"
         << "\"output\":\"" << json_escape(output_name) << "\"}";
    emit_json(json.str());
    return 0;
}

void print_help() {
    std::cout <<
        "rc522-mfc-native commands:\n"
        "  reader-version\n"
        "  identify\n"
        "  auth --block N --key-type A|B --key HEX\n"
        "  keyscan --keys FILE [--sectors 0-15]\n"
        "  nonce-probe [--block N] [--samples N]\n"
        "  weak-nested --known-block N --known-key-type A|B --known-key HEX --target-block N --target-key-type A|B\n"
        "  collect-hardnested --known-block N --known-key-type A|B --known-key HEX --target-block N --target-key-type A|B --samples N --output FILE [--meta FILE] [--validation-key HEX]\n"
        "  dump --key-map FILE --output FILE\n";
}

}  // namespace

int main(int argc, char **argv) {
    std::signal(SIGINT, on_signal);
    std::signal(SIGTERM, on_signal);
    try {
        const Args args = parse_args(argc, argv);
        if (args.command == "help" || args.command == "--help") { print_help(); return 0; }
        if (args.command == "reader-version") return command_reader_version(args);
        if (args.command == "identify") return command_identify(args);
        if (args.command == "auth") return command_auth(args);
        if (args.command == "keyscan") return command_keyscan(args);
        if (args.command == "nonce-probe") return command_nonce_probe(args);
        if (args.command == "weak-nested") return command_weak_nested(args);
        if (args.command == "collect-hardnested") return command_collect_hardnested(args);
        if (args.command == "dump") return command_dump(args);
        throw std::runtime_error("unknown command: " + args.command);
    } catch (const std::exception &error) {
        emit_json(std::string("{\"ok\":false,\"error\":\"") + json_escape(error.what()) + "\"}");
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
