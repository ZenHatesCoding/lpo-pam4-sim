// surrogate.hpp — 白盒 Ridge 双代理模型推理（train_surrogates.WhiteBoxRidge 复刻）。
//   二阶多项式特征 + 解析梯度 + JSON 权重装载（W/mu/sd/local_spacing）。
#pragma once

#include <vector>
#include <string>
#include <fstream>
#include <sstream>
#include <cmath>
#include <cstdlib>

namespace dsh {

// 二阶多项式特征（单行）：[bias, 一次项, 平方项, 交叉项]
inline std::vector<double> poly_features(const std::vector<double>& x) {
    int d = (int)x.size();
    std::vector<double> out;
    out.reserve(1 + 2 * d + d * (d - 1) / 2);
    out.push_back(1.0);
    for (int j = 0; j < d; j++) out.push_back(x[j]);                    // 一次项
    for (int j = 0; j < d; j++) out.push_back(x[j] * x[j]);             // 平方项
    for (int j = 0; j < d; j++)                                         // 交叉项
        for (int k = j + 1; k < d; k++) out.push_back(x[j] * x[k]);
    return out;
}

// 解析梯度：∂f/∂x_i = w_i + 2 w_ii x_i + Σ_{k≠i} w_ik x_k
inline std::vector<double> poly_grad(const std::vector<double>& x, const std::vector<double>& W) {
    int d = (int)x.size();
    std::vector<double> g(d, 0.0);
    for (int j = 0; j < d; j++) g[j] += W[1 + j];                       // 一次项
    for (int j = 0; j < d; j++) g[j] += 2.0 * W[1 + d + j] * x[j];      // 平方项
    int idx = 1 + 2 * d;
    for (int j = 0; j < d; j++)
        for (int k = j + 1; k < d; k++) {
            g[j] += W[idx] * x[k];
            g[k] += W[idx] * x[j];
            idx++;
        }
    return g;
}

// 最小 JSON 读取（自控导出格式：{"W":[...],"mu":[...],"sd":[...],"local_spacing":n}）
inline std::vector<double> json_array(const std::string& text, const std::string& key) {
    std::string needle = "\"" + key + "\"";
    size_t p = text.find(needle);
    if (p == std::string::npos) return {};
    size_t a = text.find('[', p);
    if (a == std::string::npos) return {};
    size_t b = text.find(']', a);
    if (b == std::string::npos) return {};
    std::string inner = text.substr(a + 1, b - a - 1);
    std::vector<double> out;
    std::stringstream ss(inner);
    std::string tok;
    while (std::getline(ss, tok, ',')) {
        try { out.push_back(std::stod(tok)); } catch (...) {}
    }
    return out;
}
inline double json_number(const std::string& text, const std::string& key, double def) {
    std::string needle = "\"" + key + "\"";
    size_t p = text.find(needle);
    if (p == std::string::npos) return def;
    p = text.find(':', p);
    if (p == std::string::npos) return def;
    const char* s = text.c_str() + p + 1;
    char* end = nullptr;
    double v = std::strtod(s, &end);
    return (end == s) ? def : v;
}

struct WhiteBoxRidge {
    int dim = 0;
    std::vector<double> W, mu, sd;
    double local_spacing = 0.0;

    // 标准化：(x - mu) / sd
    std::vector<double> standardize(const std::vector<double>& x) const {
        std::vector<double> xn(x.size());
        for (size_t i = 0; i < x.size(); i++) xn[i] = (x[i] - mu[i]) / sd[i];
        return xn;
    }
    // predict：输入**已标准化**特征（与 Python WhiteBoxRidge.predict 语义一致）
    double predict(const std::vector<double>& xn) const {
        auto p = poly_features(xn);
        double s = 0.0;
        for (size_t i = 0; i < p.size(); i++) s += p[i] * W[i];
        return s;
    }
    // 便捷：原始输入 -> 预测
    double predict_raw(const std::vector<double>& x) const { return predict(standardize(x)); }
    // 解析梯度（对标准化输入）
    std::vector<double> grad(const std::vector<double>& xn) const { return poly_grad(xn, W); }
};

inline WhiteBoxRidge load_ridge(const std::string& path) {
    std::ifstream f(path);
    std::stringstream ss;
    ss << f.rdbuf();
    std::string text = ss.str();
    WhiteBoxRidge m;
    m.W = json_array(text, "W");
    m.mu = json_array(text, "mu");
    m.sd = json_array(text, "sd");
    m.local_spacing = json_number(text, "local_spacing", 0.0);
    m.dim = (int)m.mu.size();
    return m;
}

} // namespace dsh