// Jolt Physics スモークテスト
// ビルドしたライブラリが正しくリンク・動作するか検証する

#include <Jolt/Jolt.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Core/JobSystemThreadPool.h>
#include <Jolt/Physics/PhysicsSettings.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Body/BodyInterface.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>

#include <cstdio>
#include <cstdlib>

using namespace JPH;

// レイヤー定義
namespace Layers {
    static constexpr ObjectLayer NON_MOVING = 0;
    static constexpr ObjectLayer MOVING = 1;
    static constexpr ObjectLayer NUM_LAYERS = 2;
}

namespace BroadPhaseLayers {
    static constexpr BroadPhaseLayer NON_MOVING(0);
    static constexpr BroadPhaseLayer MOVING(1);
    static constexpr uint NUM_LAYERS = 2;
}

// BroadPhaseLayerInterface 実装
class BPLayerInterfaceImpl final : public BroadPhaseLayerInterface {
public:
    uint GetNumBroadPhaseLayers() const override { return BroadPhaseLayers::NUM_LAYERS; }
    BroadPhaseLayer GetBroadPhaseLayer(ObjectLayer inLayer) const override {
        if (inLayer == Layers::NON_MOVING) return BroadPhaseLayers::NON_MOVING;
        return BroadPhaseLayers::MOVING;
    }
};

// ObjectVsBroadPhaseLayerFilter 実装
class ObjectVsBroadPhaseLayerFilterImpl final : public ObjectVsBroadPhaseLayerFilter {
public:
    bool ShouldCollide(ObjectLayer inLayer1, BroadPhaseLayer inLayer2) const override {
        if (inLayer1 == Layers::NON_MOVING) return inLayer2 == BroadPhaseLayers::MOVING;
        return true;
    }
};

// ObjectLayerPairFilter 実装
class ObjectLayerPairFilterImpl final : public ObjectLayerPairFilter {
public:
    bool ShouldCollide(ObjectLayer inLayer1, ObjectLayer inLayer2) const override {
        if (inLayer1 == Layers::NON_MOVING && inLayer2 == Layers::NON_MOVING) return false;
        return true;
    }
};

static bool test_failed = false;

#define CHECK(cond, msg) do { \
    if (!(cond)) { \
        fprintf(stderr, "FAIL: %s\n", msg); \
        test_failed = true; \
    } else { \
        printf("OK: %s\n", msg); \
    } \
} while(0)

int main() {
    printf("=== Jolt Physics Smoke Test ===\n\n");

    // 1. 初期化
    RegisterDefaultAllocator();
    Factory::sInstance = new Factory();
    RegisterTypes();

    TempAllocatorImpl temp_allocator(10 * 1024 * 1024);
    JobSystemThreadPool job_system(cMaxPhysicsJobs, cMaxPhysicsBarriers, 1);

    printf("OK: Jolt initialized\n");

    // 2. PhysicsSystem 作成
    BPLayerInterfaceImpl bp_layer_interface;
    ObjectVsBroadPhaseLayerFilterImpl obj_vs_bp_filter;
    ObjectLayerPairFilterImpl obj_pair_filter;

    PhysicsSystem physics_system;
    physics_system.Init(
        1024,   // max bodies
        0,      // num body mutexes (0 = auto)
        1024,   // max body pairs
        1024,   // max contact constraints
        bp_layer_interface,
        obj_vs_bp_filter,
        obj_pair_filter
    );

    BodyInterface &body_interface = physics_system.GetBodyInterface();
    printf("OK: PhysicsSystem created\n");

    // 3. 静的な床を作成
    BoxShapeSettings floor_shape_settings(Vec3(100.0f, 1.0f, 100.0f));
    floor_shape_settings.SetEmbedded();
    ShapeSettings::ShapeResult floor_shape_result = floor_shape_settings.Create();
    CHECK(floor_shape_result.IsValid(), "Floor shape created");

    BodyCreationSettings floor_settings(
        floor_shape_result.Get(),
        RVec3(0.0, -1.0, 0.0),
        Quat::sIdentity(),
        EMotionType::Static,
        Layers::NON_MOVING
    );
    Body *floor = body_interface.CreateBody(floor_settings);
    CHECK(floor != nullptr, "Floor body created");
    body_interface.AddBody(floor->GetID(), EActivation::DontActivate);

    // 4. 動的な球を作成 (高さ 10m から落下)
    BodyCreationSettings sphere_settings(
        new SphereShape(0.5f),
        RVec3(0.0, 10.0, 0.0),
        Quat::sIdentity(),
        EMotionType::Dynamic,
        Layers::MOVING
    );
    BodyID sphere_id = body_interface.CreateAndAddBody(sphere_settings, EActivation::Activate);
    CHECK(!sphere_id.IsInvalid(), "Sphere body created");

    RVec3 initial_pos = body_interface.GetCenterOfMassPosition(sphere_id);
    printf("  Initial position: y = %.3f\n", (double)initial_pos.GetY());

    // 5. シミュレーション実行 (1秒間 = 60ステップ)
    physics_system.OptimizeBroadPhase();

    const float dt = 1.0f / 60.0f;
    const int steps = 60;

    for (int i = 0; i < steps; i++) {
        physics_system.Update(dt, 1, &temp_allocator, &job_system);
    }

    RVec3 final_pos = body_interface.GetCenterOfMassPosition(sphere_id);
    printf("  Final position: y = %.3f\n", (double)final_pos.GetY());

    // 球は重力で落下しているはず
    CHECK(final_pos.GetY() < initial_pos.GetY(), "Sphere fell due to gravity");
    // 床 (y=0) に衝突して止まっているはず (y >= 0)
    CHECK(final_pos.GetY() >= 0.0, "Sphere stopped on floor (not fell through)");

    // 6. クリーンアップ
    body_interface.RemoveBody(sphere_id);
    body_interface.DestroyBody(sphere_id);
    body_interface.RemoveBody(floor->GetID());
    body_interface.DestroyBody(floor->GetID());

    UnregisterTypes();
    delete Factory::sInstance;
    Factory::sInstance = nullptr;

    printf("\n");
    if (test_failed) {
        printf("=== SMOKE TEST FAILED ===\n");
        return 1;
    }
    printf("=== SMOKE TEST PASSED ===\n");
    return 0;
}
